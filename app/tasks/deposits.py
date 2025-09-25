"""
Deposit processing tasks
"""

from app.celery_app import celery
from app.db.session import async_session
from sqlalchemy import select, update, text
from app.models.transaction import Transaction
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery.task(bind=True, acks_late=True)
def process_deposit(self, tx_id, payload=None):
    """
    Process a deposit transaction.
    
    Args:
        tx_id: Transaction ID
        payload: Optional webhook payload data
    """
    try:
        # Run the async processing
        result = asyncio.run(process_deposit_async(tx_id, payload))
        logger.info(f"Deposit processed successfully for tx_id: {tx_id}")
        return result
    except Exception as e:
        logger.error(f"Error processing deposit for tx_id {tx_id}: {e}")
        raise


async def process_deposit_async(tx_id, payload=None):
    """
    Async helper for deposit processing.
    
    Args:
        tx_id: Transaction ID
        payload: Optional webhook payload data
    
    Returns:
        bool: True if successful
    """
    async with async_session() as db:
        try:
            # Update transaction metadata to mark as processed
            await db.execute(
                text("UPDATE transactions SET metadata = metadata || '{\"status\": \"processed\"}' WHERE id = :tx_id"),
                {"tx_id": tx_id}
            )
            await db.commit()
            
            logger.info(f"Transaction {tx_id} marked as processed")
            
            # Send notification to user
            from app.tasks.notify import send_deposit_confirmation
            await send_deposit_confirmation(tx_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in async deposit processing for tx_id {tx_id}: {e}")
            await db.rollback()
            raise


# Create an async helper so unit tests can call it
async def _dummy():
    """Dummy async function for testing"""
    pass