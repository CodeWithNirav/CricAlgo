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

from app.core.config import settings
from app.db.session import get_db
from app.repos.transaction_repo import get_transactions_by_user, update_transaction_metadata
from app.repos.wallet_repo import get_wallet_for_user, update_balances_atomic
from app.repos.user_repo import get_user_by_id
from app.tasks.tasks import process_deposit
from tests.fixtures.redis import RedisTestHelper

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookPayload(BaseModel):
    """Webhook payload model for blockchain confirmations"""
    tx_hash: str = Field(..., description="Transaction hash")
    confirmations: int = Field(..., description="Number of confirmations")
    amount: Optional[str] = Field(None, description="Transaction amount")
    currency: Optional[str] = Field(default="USDT", description="Currency code")
    status: Optional[str] = Field(default="confirmed", description="Transaction status")
    block_number: Optional[int] = Field(None, description="Block number")
    user_id: Optional[str] = Field(None, description="User ID (if known)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class WebhookResponse(BaseModel):
    """Webhook response model"""
    success: bool
    message: str
    tx_hash: str


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
    
    signature = request.headers.get("X-Signature")
    if not signature:
        return False
    
    expected_signature = hmac.new(
        settings.webhook_secret.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


async def check_webhook_idempotency(redis_client, tx_hash: str) -> bool:
    """
    Check if webhook has already been processed.
    
    Args:
        redis_client: Redis client
        tx_hash: Transaction hash
    
    Returns:
        True if already processed, False otherwise
    """
    try:
        helper = RedisTestHelper(redis_client)
        return await helper.check_idempotency_key(tx_hash)
    except Exception as e:
        logger.error(f"Error checking idempotency for {tx_hash}: {e}")
        return False


async def mark_webhook_processed(redis_client, tx_hash: str) -> bool:
    """
    Mark webhook as processed.
    
    Args:
        redis_client: Redis client
        tx_hash: Transaction hash
    
    Returns:
        True if marked successfully, False otherwise
    """
    try:
        helper = RedisTestHelper(redis_client)
        return await helper.set_idempotency_key(tx_hash, ttl=3600)
    except Exception as e:
        logger.error(f"Error marking {tx_hash} as processed: {e}")
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
    and updates user wallet balances accordingly.
    """
    try:
        tx_hash = payload.tx_hash
        logger.info(f"Received BEP20 webhook for tx_hash: {tx_hash}")
        
        # Verify webhook signature if secret is configured
        body = await request.body()
        if not verify_webhook_signature(request, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Check idempotency
        # TODO: Get Redis client from dependency injection
        redis_client = None  # This would be injected in a real implementation
        if redis_client:
            if await check_webhook_idempotency(redis_client, tx_hash):
                logger.info(f"Transaction {tx_hash} already processed, skipping")
                return WebhookResponse(
                    success=True,
                    message="Transaction already processed",
                    tx_hash=tx_hash
                )
        
        # Validate webhook payload
        if not tx_hash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tx_hash is required")
        
        if payload.confirmations < settings.confirmation_threshold:
            logger.info(f"Transaction {tx_hash} has insufficient confirmations: {payload.confirmations}")
            return WebhookResponse(
                success=True,
                message="Transaction pending - insufficient confirmations",
                tx_hash=tx_hash
            )
        
        # Process based on transaction status
        success = False
        
        if payload.status == "confirmed":
            # Process deposit confirmation
            if payload.user_id:
                user_id = UUID(payload.user_id)
                user = await get_user_by_id(session, user_id)
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="User not found"
                    )
                
                # Get user's wallet
                wallet = await get_wallet_for_user(session, user_id)
                if not wallet:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Wallet not found"
                    )
                
                # Process deposit
                amount = Decimal(payload.amount or "0")
                if amount > 0:
                    success, error = await update_balances_atomic(
                        session,
                        user_id,
                        deposit_delta=amount
                    )
                    
                    if not success:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update wallet: {error}"
                        )
                    
                    # Create deposit transaction
                    from app.repos.transaction_repo import create_transaction
                    await create_transaction(
                        session=session,
                        user_id=user_id,
                        tx_type="deposit",
                        amount=amount,
                        currency=payload.currency or settings.currency,
                        tx_metadata={
                            "tx_hash": tx_hash,
                            "confirmations": payload.confirmations,
                            "block_number": payload.block_number,
                            "status": "confirmed"
                        }
                    )
                    
                    logger.info(f"Successfully processed deposit {tx_hash} for user {user_id}, amount: {amount}")
                    success = True
                else:
                    success = True  # No amount to process
            else:
                # Enqueue deposit processing task for unknown user
                process_deposit.delay(tx_hash, payload.amount or "0", payload.currency or settings.currency)
                success = True
                
        elif payload.status == "failed":
            logger.info(f"Transaction {tx_hash} failed, no balance update needed")
            success = True
        else:
            logger.warning(f"Unknown transaction status: {payload.status}")
            success = False
        
        # Mark as processed (if Redis is available)
        if redis_client and success:
            await mark_webhook_processed(redis_client, tx_hash)
        
        if success:
            return WebhookResponse(
                success=True,
                message="Webhook processed successfully",
                tx_hash=tx_hash
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process webhook"
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
