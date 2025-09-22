"""
Async webhook processing tasks
"""

import logging
from decimal import Decimal
from typing import Dict, Any
from uuid import UUID

from app.celery_app import celery
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.repos.transaction_repo import create_transaction
from app.models.transaction import Transaction
from app.tasks.deposits import process_deposit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery.task(bind=True, name="app.tasks.webhook_processing.process_webhook_async")
def process_webhook_async(self, tx_hash: str, payload_data: Dict[str, Any]):
    """
    Process webhook asynchronously.
    
    This task handles the heavy processing of webhook data
    that was previously done synchronously in the webhook endpoint.
    """
    logger.info(f"Starting async webhook processing for tx_hash: {tx_hash}")
    
    try:
        # Create async session for database operations
        import asyncio
        
        async def _process():
            async with AsyncSessionLocal() as session:
                # Look up or create transaction
                existing_tx = None
                
                # Try to find existing transaction by hash
                if payload_data.get("tx_metadata") and "tx_hash" in payload_data["tx_metadata"]:
                    result = await session.execute(
                        select(Transaction).where(
                            Transaction.tx_metadata["tx_hash"].astext == tx_hash
                        )
                    )
                    existing_tx = result.scalar_one_or_none()
                
                # If not found and we have user_id, create transaction
                if not existing_tx and payload_data.get("user_id"):
                    try:
                        user_id = UUID(payload_data["user_id"])
                        amount = Decimal(payload_data.get("amount", "0"))
                        
                        existing_tx = await create_transaction(
                            session=session,
                            user_id=user_id,
                            tx_type="deposit",
                            amount=amount,
                            currency=payload_data.get("currency", settings.currency),
                            tx_metadata={
                                "tx_hash": tx_hash,
                                "confirmations": payload_data.get("confirmations", 0),
                                "block_number": payload_data.get("block_number"),
                                "to_address": payload_data.get("to_address"),
                                "chain": payload_data.get("chain", "bep20"),
                                "status": "pending"
                            }
                        )
                        logger.info(f"Created new transaction {existing_tx.id} for tx_hash: {tx_hash}")
                    except Exception as e:
                        logger.error(f"Failed to create transaction for {tx_hash}: {e}")
                        return False
                
                # Update confirmations if transaction exists
                if existing_tx:
                    # Update confirmations in metadata
                    if not existing_tx.tx_metadata:
                        existing_tx.tx_metadata = {}

                    existing_tx.tx_metadata.update({
                        "confirmations": payload_data.get("confirmations", 0),
                        "block_number": payload_data.get("block_number"),
                        "to_address": payload_data.get("to_address"),
                        "chain": payload_data.get("chain", "bep20")
                    })
                    
                    await session.commit()
                    logger.info(f"Updated confirmations for transaction {existing_tx.id}: {payload_data.get('confirmations', 0)}")
                
                # Check if we should enqueue processing
                confirmations = payload_data.get("confirmations", 0)
                if confirmations >= settings.confirmation_threshold:
                    # Get Redis client
                    redis_client = await get_redis_client()
                    
                    if redis_client:
                        # Check if already enqueued
                        from app.api.v1.webhooks import check_deposit_processing_idempotency, mark_deposit_processing_enqueued
                        
                        if await check_deposit_processing_idempotency(redis_client, tx_hash):
                            logger.info(f"Deposit processing already enqueued for {tx_hash}")
                            return True
                        
                        # Mark as enqueued
                        if await mark_deposit_processing_enqueued(redis_client, tx_hash):
                            # Enqueue the deposit processing task
                            if existing_tx:
                                process_deposit.delay(str(existing_tx.id))
                                logger.info(f"Enqueued deposit processing for transaction {existing_tx.id}")
                                return True
                            else:
                                logger.warning(f"No transaction found to process for {tx_hash}")
                                return False
                        else:
                            logger.error(f"Failed to mark deposit processing as enqueued for {tx_hash}")
                            return False
                    else:
                        logger.warning("Redis not available, cannot ensure idempotency")
                        return False
                else:
                    logger.info(f"Confirmations {confirmations} below threshold {settings.confirmation_threshold}, not processing yet")
                    return True
                
        # Run the async function
        result = asyncio.run(_process())
        
        if result:
            logger.info(f"Successfully processed webhook for tx_hash: {tx_hash}")
        else:
            logger.error(f"Failed to process webhook for tx_hash: {tx_hash}")
            
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error in async webhook processing for {tx_hash}: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)
