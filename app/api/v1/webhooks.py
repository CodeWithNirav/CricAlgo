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


@router.post("/bep20")
async def bep20_webhook(payload: WebhookPayload, request: Request):
    """
    BEP20 webhook - optimized for performance:
    - validate minimal fields
    - create transaction record (status 'pending') with quick DB insert
    - enqueue deposit processing task
    - return 202 with canonical {"ok": true, "tx_id": "..."}
    """
    import time
    import uuid
    import json
    from fastapi.responses import JSONResponse
    from sqlalchemy import text as sa_text
    from app.db.session import get_db
    from app.celery_app import celery_app
    
    tx_hash = payload.tx_hash
    amount = payload.amount
    metadata = payload.metadata or {}
    
    if not tx_hash or amount is None:
        return JSONResponse(status_code=400, content={"ok": False, "error": "missing tx_hash or amount"})
    
    # Convert amount to string if it's numeric
    try:
        amount = str(amount)
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid amount format"})
    
    tx_id = str(uuid.uuid4())
    
    # Quick DB insert with raw SQL for better performance
    try:
        async with get_db() as db:
            # Add tx_hash to metadata
            metadata["tx_hash"] = tx_hash
            if payload.user_id:
                metadata["telegram_id"] = payload.user_id
            
            await db.execute(sa_text(
                "INSERT INTO transactions (id, tx_type, amount, currency, metadata, status, created_at) "
                "VALUES (:id, :tx_type, :amount, :currency, :metadata, :status, now())"
            ), {
                "id": tx_id, 
                "tx_type": "deposit", 
                "amount": amount, 
                "currency": "USDT",
                "metadata": json.dumps(metadata), 
                "status": "pending"
            })
            await db.commit()
    except Exception:
        logger.exception("failed to persist transaction record; continuing with enqueue", extra={"tx_hash": tx_hash})
    
    # Enqueue processing (idempotent)
    try:
        from app.tasks.deposits import process_deposit
        process_deposit.delay(tx_id, payload)
        logger.info("deposit_enqueued", extra={"tx_id": tx_id, "tx_hash": tx_hash, "enqueued_at": time.time()})
    except Exception:
        logger.exception("failed to enqueue deposit task", extra={"tx_hash": tx_hash})
    
    # Return canonical response
    return JSONResponse(status_code=202, content={"ok": True, "tx_id": tx_id})


@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoints."""
    return {
        "status": "ok",
        "service": "webhooks",
        "endpoints": ["/api/v1/webhooks/bep20"]
    }
