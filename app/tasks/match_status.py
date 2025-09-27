"""
Match status management tasks
"""

import logging
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery
from app.db.session import AsyncSessionLocal
from app.repos.match_repo import update_match_statuses_automatically, get_matches_needing_status_update

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def update_match_statuses_task(self):
    """
    Automatically update match statuses based on start time.
    This task should be run periodically (e.g., every 5 minutes).
    """
    try:
        logger.info("Starting match status update task")
        
        async def _process():
            async with AsyncSessionLocal() as session:
                # Update match statuses automatically
                updated_count = await update_match_statuses_automatically(session)
                
                if updated_count > 0:
                    logger.info(f"Updated {updated_count} match statuses")
                else:
                    logger.info("No match statuses needed updating")
                
                return updated_count
        
        # Run async function
        import asyncio
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a new event loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _process())
                return future.result()
        except RuntimeError:
            # No event loop running, use asyncio.run()
            return asyncio.run(_process())
        
    except Exception as exc:
        logger.error(f"Error updating match statuses: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying match status update (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        else:
            logger.error("Max retries exceeded for match status update")
            raise


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def mark_match_as_finished_task(self, match_id: str, admin_id: str = None):
    """
    Mark a match as finished (admin action).
    
    Args:
        match_id: Match ID as string
        admin_id: Admin ID who marked the match as finished
    """
    try:
        logger.info(f"Marking match {match_id} as finished")
        
        async def _process():
            from app.repos.match_repo import update_match_status
            from app.repos.audit_log_repo import create_audit_log
            
            async with AsyncSessionLocal() as session:
                # Update match status to 'finished'
                success = await update_match_status(session, match_id, 'finished')
                
                if success:
                    # Create audit log
                    await create_audit_log(
                        session=session,
                        admin_id=admin_id,
                        action="mark_match_finished",
                        resource_type="match",
                        resource_id=match_id,
                        details={
                            "match_id": match_id,
                            "new_status": "finished",
                            "admin_id": admin_id
                        }
                    )
                    logger.info(f"Successfully marked match {match_id} as finished")
                else:
                    logger.error(f"Failed to mark match {match_id} as finished")
                
                return success
        
        # Run async function
        import asyncio
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a new event loop in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _process())
                return future.result()
        except RuntimeError:
            # No event loop running, use asyncio.run()
            return asyncio.run(_process())
        
    except Exception as exc:
        logger.error(f"Error marking match {match_id} as finished: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying mark match as finished for {match_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        else:
            logger.error(f"Max retries exceeded for marking match {match_id} as finished")
            raise
