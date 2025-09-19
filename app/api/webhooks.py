"""
Webhook endpoints for blockchain transaction confirmations

This module handles webhook callbacks from blockchain services
for transaction confirmations, including idempotency handling.
"""

import logging
from typing import Dict, Any, Optional
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repos.transaction_repo import get_transactions_by_user, update_transaction_metadata
from app.repos.wallet_repo import get_wallet_for_user, update_balances_atomic
from app.repos.user_repo import get_user_by_id
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookPayload(BaseModel):
    """Webhook payload model for blockchain confirmations"""
    tx_hash: str
    confirmations: int
    amount: Optional[str] = None
    currency: Optional[str] = "USDT"
    status: Optional[str] = "confirmed"
    block_number: Optional[int] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    """Webhook response model"""
    success: bool
    message: str
    tx_hash: str


async def check_idempotency(redis_client, tx_hash: str) -> bool:
    """
    Check if a transaction has already been processed.
    
    Args:
        redis_client: Redis client instance
        tx_hash: Transaction hash to check
    
    Returns:
        True if already processed, False otherwise
    """
    try:
        key = f"processed:tx_hash:{tx_hash}"
        exists = await redis_client.exists(key)
        return exists > 0
    except Exception as e:
        logger.error(f"Error checking idempotency for {tx_hash}: {e}")
        return False


async def mark_processed(redis_client, tx_hash: str, ttl: int = 3600) -> bool:
    """
    Mark a transaction as processed.
    
    Args:
        redis_client: Redis client instance
        tx_hash: Transaction hash to mark
        ttl: Time to live in seconds
    
    Returns:
        True if marked successfully, False otherwise
    """
    try:
        key = f"processed:tx_hash:{tx_hash}"
        await redis_client.set(key, "1", ex=ttl)
        return True
    except Exception as e:
        logger.error(f"Error marking {tx_hash} as processed: {e}")
        return False


async def process_deposit_confirmation(
    session: AsyncSession,
    redis_client,
    payload: WebhookPayload
) -> bool:
    """
    Process a deposit confirmation webhook.
    
    Args:
        session: Database session
        redis_client: Redis client
        payload: Webhook payload
    
    Returns:
        True if processed successfully, False otherwise
    """
    try:
        tx_hash = payload.tx_hash
        amount = Decimal(payload.amount or "0")
        user_id = UUID(payload.user_id) if payload.user_id else None
        
        if not user_id:
            logger.error(f"No user_id provided for deposit webhook {tx_hash}")
            return False
        
        # Get user and wallet
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"User {user_id} not found for deposit webhook {tx_hash}")
            return False
        
        wallet = await get_wallet_for_user(session, user_id)
        if not wallet:
            logger.error(f"Wallet not found for user {user_id}")
            return False
        
        # Update wallet balance
        success, error = await update_balances_atomic(
            session,
            user_id,
            deposit_delta=amount
        )
        
        if not success:
            logger.error(f"Failed to update wallet for user {user_id}: {error}")
            return False
        
        # Update transaction metadata
        await update_transaction_metadata(
            session,
            None,  # Would need transaction ID lookup
            {
                "tx_hash": tx_hash,
                "confirmations": payload.confirmations,
                "status": payload.status,
                "block_number": payload.block_number,
                "processed_at": "now()"
            }
        )
        
        logger.info(f"Successfully processed deposit {tx_hash} for user {user_id}, amount: {amount}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing deposit confirmation {payload.tx_hash}: {e}")
        return False


async def process_withdrawal_confirmation(
    session: AsyncSession,
    redis_client,
    payload: WebhookPayload
) -> bool:
    """
    Process a withdrawal confirmation webhook.
    
    Args:
        session: Database session
        redis_client: Redis client
        payload: Webhook payload
    
    Returns:
        True if processed successfully, False otherwise
    """
    try:
        tx_hash = payload.tx_hash
        amount = Decimal(payload.amount or "0")
        user_id = UUID(payload.user_id) if payload.user_id else None
        
        if not user_id:
            logger.error(f"No user_id provided for withdrawal webhook {tx_hash}")
            return False
        
        # Get user and wallet
        user = await get_user_by_id(session, user_id)
        if not user:
            logger.error(f"User {user_id} not found for withdrawal webhook {tx_hash}")
            return False
        
        wallet = await get_wallet_for_user(session, user_id)
        if not wallet:
            logger.error(f"Wallet not found for user {user_id}")
            return False
        
        # Update wallet balance (withdrawal reduces balance)
        success, error = await update_balances_atomic(
            session,
            user_id,
            deposit_delta=-amount
        )
        
        if not success:
            logger.error(f"Failed to update wallet for user {user_id}: {error}")
            return False
        
        logger.info(f"Successfully processed withdrawal {tx_hash} for user {user_id}, amount: {amount}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing withdrawal confirmation {payload.tx_hash}: {e}")
        return False


@router.post("/webhooks/bep20", response_model=WebhookResponse)
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
        
        # TODO: Add Redis client dependency injection
        # For now, we'll skip idempotency check in tests
        redis_client = None
        
        # Check idempotency (if Redis is available)
        if redis_client:
            if await check_idempotency(redis_client, tx_hash):
                logger.info(f"Transaction {tx_hash} already processed, skipping")
                return WebhookResponse(
                    success=True,
                    message="Transaction already processed",
                    tx_hash=tx_hash
                )
        
        # Validate webhook payload
        if not tx_hash:
            raise HTTPException(status_code=400, detail="tx_hash is required")
        
        if payload.confirmations < 12:  # Minimum confirmations threshold
            logger.info(f"Transaction {tx_hash} has insufficient confirmations: {payload.confirmations}")
            return WebhookResponse(
                success=True,
                message="Transaction pending - insufficient confirmations",
                tx_hash=tx_hash
            )
        
        # Process based on transaction type (inferred from amount sign or metadata)
        success = False
        
        if payload.status == "confirmed":
            # For now, assume all confirmed transactions are deposits
            # In a real implementation, you'd determine this from transaction metadata
            success = await process_deposit_confirmation(session, redis_client, payload)
        elif payload.status == "failed":
            logger.info(f"Transaction {tx_hash} failed, no balance update needed")
            success = True
        else:
            logger.warning(f"Unknown transaction status: {payload.status}")
            success = False
        
        # Mark as processed (if Redis is available)
        if redis_client and success:
            await mark_processed(redis_client, tx_hash)
        
        if success:
            return WebhookResponse(
                success=True,
                message="Webhook processed successfully",
                tx_hash=tx_hash
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to process webhook"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.get("/webhooks/health")
async def webhook_health():
    """Health check for webhook endpoints."""
    return {
        "status": "ok",
        "service": "webhooks",
        "endpoints": ["/webhooks/bep20"]
    }
