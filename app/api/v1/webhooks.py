"""
Webhook API endpoints for blockchain confirmations
"""

import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.repos.transaction_repo import get_transactions_by_user, update_transaction_metadata
from app.repos.wallet_repo import get_wallet_for_user, update_balances_atomic
from app.repos.user_repo import get_user_by_id
from app.tasks.deposits import process_deposit
from app.core.redis_client import get_redis_helper, get_redis

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookPayload(BaseModel):
    """Webhook payload model for blockchain confirmations"""
    tx_hash: str = Field(..., description="Transaction hash")
    confirmations: int = Field(..., description="Number of confirmations")
    chain: str = Field(default="bep20", description="Blockchain network")
    to_address: Optional[str] = Field(None, description="Recipient address")
    amount: Optional[str] = Field(None, description="Transaction amount")
    currency: Optional[str] = Field(default="USDT", description="Currency code")
    status: Optional[str] = Field(default="confirmed", description="Transaction status")
    block_number: Optional[int] = Field(None, description="Block number")
    user_id: Optional[str] = Field(None, description="User ID (if known)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class WebhookResponse(BaseModel):
    """Webhook response model"""
    ok: bool
    enqueued: bool
    message: Optional[str] = None


def verify_webhook_signature(request: Request, body: bytes) -> bool:
    """
    Verify webhook signature using HMAC-SHA256.
    
    Args:
        request: FastAPI request object
        body: Raw request body
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not settings.webhook_secret:
        # If no secret is configured, skip verification
        return True
    
    # Check for both X-Signature and X-Hub-Signature-256 headers
    signature = request.headers.get("X-Signature") or request.headers.get("X-Hub-Signature-256")
    if not signature:
        return False
    
    # Remove 'sha256=' prefix if present
    if signature.startswith("sha256="):
        signature = signature[7:]
    
    expected_signature = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


async def check_deposit_processing_idempotency(redis_client, tx_hash: str) -> bool:
    """
    Check if deposit processing has already been enqueued for this transaction.
    
    Args:
        redis_client: Redis client
        tx_hash: Transaction hash
    
    Returns:
        True if already enqueued, False otherwise
    """
    try:
        key = f"deposit:tx_hash:{tx_hash}"
        return await redis_client.exists(key) > 0
    except Exception as e:
        logger.error(f"Error checking deposit processing idempotency for {tx_hash}: {e}")
        return False


async def mark_deposit_processing_enqueued(redis_client, tx_hash: str) -> bool:
    """
    Mark deposit processing as enqueued for this transaction.
    
    Args:
        redis_client: Redis client
        tx_hash: Transaction hash
    
    Returns:
        True if marked successfully, False otherwise
    """
    try:
        key = f"deposit:tx_hash:{tx_hash}"
        # Use SETNX to ensure atomic operation
        return await redis_client.set(key, "1", nx=True, ex=86400)  # 24 hour TTL
    except Exception as e:
        logger.error(f"Error marking deposit processing as enqueued for {tx_hash}: {e}")
        return False


@router.post("/bep20", response_model=WebhookResponse)
async def receive_bep20_webhook(
    payload: WebhookPayload,
    request: Request,
    session: AsyncSession = Depends(get_db)
):
    """
    Receive BEP20 (BSC) transaction confirmation webhooks.
    
    This endpoint processes blockchain transaction confirmations
    and enqueues deposit processing when confirmation threshold is met.
    """
    try:
        tx_hash = payload.tx_hash
        logger.info(f"Received BEP20 webhook for tx_hash: {tx_hash}, confirmations: {payload.confirmations}")
        
        # Verify webhook signature if secret is configured
        body = await request.body()
        if not verify_webhook_signature(request, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Validate webhook payload
        if not tx_hash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tx_hash is required")
        
        # Get Redis client
        redis_client = await get_redis()
        
        # Look up or create transaction
        from app.repos.transaction_repo import get_transaction_by_hash, create_transaction
        from app.models.transaction import Transaction
        
        # Try to find existing transaction by hash
        existing_tx = None
        if payload.tx_metadata and "tx_hash" in payload.tx_metadata:
            # Search by tx_hash in metadata
            result = await session.execute(
                select(Transaction).where(
                    Transaction.tx_metadata["tx_hash"].astext == tx_hash
                )
            )
            existing_tx = result.scalar_one_or_none()
        
        # If not found and we have user_id, create transaction
        if not existing_tx and payload.user_id:
            try:
                user_id = UUID(payload.user_id)
                amount = Decimal(payload.amount or "0")
                
                existing_tx = await create_transaction(
                    session=session,
                    user_id=user_id,
                    tx_type="deposit",
                    amount=amount,
                    currency=payload.currency or settings.currency,
                    tx_metadata={
                        "tx_hash": tx_hash,
                        "confirmations": payload.confirmations,
                        "block_number": payload.block_number,
                        "to_address": payload.to_address,
                        "chain": payload.chain,
                        "status": "pending"
                    }
                )
                logger.info(f"Created new transaction {existing_tx.id} for tx_hash: {tx_hash}")
            except Exception as e:
                logger.error(f"Failed to create transaction for {tx_hash}: {e}")
                # Continue without creating transaction
        
        # Update confirmations if transaction exists
        if existing_tx:
            # Update confirmations in metadata
            if not existing_tx.tx_metadata:
                existing_tx.tx_metadata = {}

            existing_tx.tx_metadata.update({
                "confirmations": payload.confirmations,
                "block_number": payload.block_number,
                "to_address": payload.to_address,
                "chain": payload.chain
            })
            
            await session.commit()
            logger.info(f"Updated confirmations for transaction {existing_tx.id}: {payload.confirmations}")
        
        # Check if we should enqueue processing
        enqueued = False
        if payload.confirmations >= settings.confirmation_threshold:
            if redis_client:
                # Check if already enqueued
                if await check_deposit_processing_idempotency(redis_client, tx_hash):
                    logger.info(f"Deposit processing already enqueued for {tx_hash}")
                    return WebhookResponse(ok=True, enqueued=False, message="Already enqueued")
                
                # Mark as enqueued
                if await mark_deposit_processing_enqueued(redis_client, tx_hash):
                    # Enqueue the task
                    if existing_tx:
                        process_deposit.delay(str(existing_tx.id))
                        enqueued = True
                        logger.info(f"Enqueued deposit processing for transaction {existing_tx.id}")
                    else:
                        logger.warning(f"No transaction found to process for {tx_hash}")
                else:
                    logger.error(f"Failed to mark deposit processing as enqueued for {tx_hash}")
            else:
                logger.warning("Redis not available, cannot ensure idempotency")
        
        return WebhookResponse(
            ok=True,
            enqueued=enqueued,
            message="Webhook processed successfully"
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoints."""
    return {
        "status": "ok",
        "service": "webhooks",
        "endpoints": ["/api/v1/webhooks/bep20"]
    }
