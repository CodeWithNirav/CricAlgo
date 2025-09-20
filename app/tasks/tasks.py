"""
Celery background tasks
"""

import logging
from decimal import Decimal
from typing import Dict, Any
from uuid import UUID

from celery import current_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repos.transaction_repo import get_transaction_by_id, update_transaction_metadata
from app.repos.wallet_repo import get_wallet_for_user, update_balances_atomic
from app.repos.contest_repo import get_contest_by_id, settle_contest
from app.repos.contest_entry_repo import get_contest_entries
from app.repos.audit_log_repo import create_audit_log
from app.services.blockchain import verify_transaction

# Configure logging
logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_deposit(self, tx_hash: str, amount: str, currency: str = "USDT"):
    """
    Process a deposit transaction.
    
    Args:
        tx_hash: Transaction hash
        amount: Deposit amount as string
        currency: Currency code
    """
    try:
        logger.info(f"Processing deposit: {tx_hash}, amount: {amount} {currency}")
        
        # Verify transaction with blockchain provider
        verification_result = verify_transaction(tx_hash)
        
        if not verification_result.get("success", False):
            logger.error(f"Transaction verification failed for {tx_hash}")
            raise Exception(f"Transaction verification failed: {verification_result.get('error', 'Unknown error')}")
        
        # Check if transaction has sufficient confirmations
        confirmations = verification_result.get("confirmations", 0)
        if confirmations < settings.confirmation_threshold:
            logger.info(f"Transaction {tx_hash} has insufficient confirmations: {confirmations}")
            # Retry later
            raise self.retry(countdown=300)  # Retry in 5 minutes
        
        # Process the deposit
        async def _process():
            async with AsyncSessionLocal() as session:
                # Find transaction by hash
                from app.repos.transaction_repo import get_transactions_by_type
                transactions = await get_transactions_by_type(session, "deposit", limit=1000)
                
                # Find transaction with matching hash
                target_transaction = None
                for tx in transactions:
                    if tx.tx_metadata and tx.tx_metadata.get("tx_hash") == tx_hash:
                        target_transaction = tx
                        break
                
                if not target_transaction:
                    logger.error(f"Transaction not found in database: {tx_hash}")
                    return False
                
                # Check if already processed
                current_status = target_transaction.tx_metadata.get("status", "pending") if target_transaction.tx_metadata else "pending"
                if current_status == "confirmed":
                    logger.info(f"Transaction {tx_hash} already processed")
                    return True
                
                # Update wallet balance
                deposit_amount = Decimal(amount)
                success, error = await update_balances_atomic(
                    session,
                    target_transaction.user_id,
                    deposit_delta=deposit_amount
                )
                
                if not success:
                    logger.error(f"Failed to update wallet for transaction {tx_hash}: {error}")
                    return False
                
                # Update transaction status
                await update_transaction_metadata(
                    session,
                    target_transaction.id,
                    {
                        **target_transaction.tx_metadata,
                        "status": "confirmed",
                        "confirmations": confirmations,
                        "processed_at": "now()"
                    }
                )
                
                # Create audit log
                await create_audit_log(
                    session=session,
                    admin_id=target_transaction.user_id,  # System user
                    action="process_deposit",
                    resource_type="transaction",
                    resource_id=target_transaction.id,
                    details={
                        "tx_hash": tx_hash,
                        "amount": str(deposit_amount),
                        "currency": currency,
                        "confirmations": confirmations
                    }
                )
                
                logger.info(f"Successfully processed deposit {tx_hash} for user {target_transaction.user_id}")
                return True
        
        # Run async function
        import asyncio
        return asyncio.run(_process())
        
    except Exception as exc:
        logger.error(f"Error processing deposit {tx_hash}: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying deposit processing for {tx_hash} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        else:
            logger.error(f"Max retries exceeded for deposit {tx_hash}")
            raise


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def process_withdrawal(self, transaction_id: str):
    """
    Process a withdrawal transaction.
    
    Args:
        transaction_id: Transaction UUID as string
    """
    try:
        logger.info(f"Processing withdrawal: {transaction_id}")
        
        async def _process():
            async with AsyncSessionLocal() as session:
                tx_uuid = UUID(transaction_id)
                transaction = await get_transaction_by_id(session, tx_uuid)
                
                if not transaction:
                    logger.error(f"Transaction not found: {transaction_id}")
                    return False
                
                if transaction.tx_type != "withdrawal":
                    logger.error(f"Transaction {transaction_id} is not a withdrawal")
                    return False
                
                # Check if already processed
                current_status = transaction.tx_metadata.get("status", "pending") if transaction.tx_metadata else "pending"
                if current_status in ["processing", "completed", "failed"]:
                    logger.info(f"Transaction {transaction_id} already processed with status: {current_status}")
                    return True
                
                # Update status to processing
                await update_transaction_metadata(
                    session,
                    tx_uuid,
                    {
                        **transaction.tx_metadata,
                        "status": "processing",
                        "processed_at": "now()"
                    }
                )
                
                # Simulate external withdrawal processing
                # In a real implementation, this would call an external API
                withdrawal_address = transaction.tx_metadata.get("withdrawal_address") if transaction.tx_metadata else None
                
                if not withdrawal_address:
                    logger.error(f"No withdrawal address for transaction {transaction_id}")
                    await update_transaction_metadata(
                        session,
                        tx_uuid,
                        {
                            **transaction.tx_metadata,
                            "status": "failed",
                            "error": "No withdrawal address provided"
                        }
                    )
                    return False
                
                # Simulate processing delay
                import time
                time.sleep(2)  # Simulate API call delay
                
                # Simulate success (in real implementation, check external API response)
                success = True  # This would be determined by external API response
                
                if success:
                    # Update status to completed
                    await update_transaction_metadata(
                        session,
                        tx_uuid,
                        {
                            **transaction.tx_metadata,
                            "status": "completed",
                            "external_tx_hash": f"ext_{tx_uuid}",  # Simulated external transaction hash
                            "completed_at": "now()"
                        }
                    )
                    
                    logger.info(f"Successfully processed withdrawal {transaction_id}")
                else:
                    # Update status to failed
                    await update_transaction_metadata(
                        session,
                        tx_uuid,
                        {
                            **transaction.tx_metadata,
                            "status": "failed",
                            "error": "External withdrawal failed"
                        }
                    )
                    
                    logger.error(f"Failed to process withdrawal {transaction_id}")
                
                # Create audit log
                await create_audit_log(
                    session=session,
                    admin_id=transaction.user_id,  # System user
                    action="process_withdrawal",
                    resource_type="transaction",
                    resource_id=tx_uuid,
                    details={
                        "transaction_id": transaction_id,
                        "amount": str(transaction.amount),
                        "currency": transaction.currency,
                        "withdrawal_address": withdrawal_address,
                        "status": "completed" if success else "failed"
                    }
                )
                
                return success
        
        # Run async function
        import asyncio
        return asyncio.run(_process())
        
    except Exception as exc:
        logger.error(f"Error processing withdrawal {transaction_id}: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying withdrawal processing for {transaction_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        else:
            logger.error(f"Max retries exceeded for withdrawal {transaction_id}")
            raise


@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def compute_and_distribute_payouts(self, contest_id: str):
    """
    Compute and distribute contest payouts.
    
    Args:
        contest_id: Contest UUID as string
    """
    try:
        logger.info(f"Computing payouts for contest: {contest_id}")
        
        async def _process():
            async with AsyncSessionLocal() as session:
                contest_uuid = UUID(contest_id)
                contest = await get_contest_by_id(session, contest_uuid)
                
                if not contest:
                    logger.error(f"Contest not found: {contest_id}")
                    return False
                
                # Get contest entries
                entries = await get_contest_entries(session, contest_uuid)
                
                if not entries:
                    logger.error(f"No entries found for contest {contest_id}")
                    return False
                
                # Calculate total prize pool
                total_entry_fees = sum(entry.amount_debited for entry in entries)
                commission_rate = Decimal(str(settings.platform_commission_pct / 100))
                total_commission = total_entry_fees * commission_rate
                prize_pool = total_entry_fees - total_commission
                
                logger.info(f"Contest {contest_id}: {len(entries)} entries, prize pool: {prize_pool}, commission: {total_commission}")
                
                # Distribute prizes based on prize structure
                prize_structure = contest.prize_structure
                total_distributed = Decimal('0')
                
                # Simple prize distribution (in real implementation, this would be more complex)
                if len(entries) >= 1:
                    # First place gets 50% of prize pool
                    first_place_amount = prize_pool * Decimal('0.5')
                    first_place_user = entries[0].user_id
                    
                    success, error = await update_balances_atomic(
                        session,
                        first_place_user,
                        winning_delta=first_place_amount
                    )
                    
                    if success:
                        total_distributed += first_place_amount
                        logger.info(f"Distributed {first_place_amount} to first place user {first_place_user}")
                    else:
                        logger.error(f"Failed to distribute first place prize: {error}")
                
                if len(entries) >= 2:
                    # Second place gets 30% of prize pool
                    second_place_amount = prize_pool * Decimal('0.3')
                    second_place_user = entries[1].user_id
                    
                    success, error = await update_balances_atomic(
                        session,
                        second_place_user,
                        winning_delta=second_place_amount
                    )
                    
                    if success:
                        total_distributed += second_place_amount
                        logger.info(f"Distributed {second_place_amount} to second place user {second_place_user}")
                    else:
                        logger.error(f"Failed to distribute second place prize: {error}")
                
                if len(entries) >= 3:
                    # Third place gets 20% of prize pool
                    third_place_amount = prize_pool * Decimal('0.2')
                    third_place_user = entries[2].user_id
                    
                    success, error = await update_balances_atomic(
                        session,
                        third_place_user,
                        winning_delta=third_place_amount
                    )
                    
                    if success:
                        total_distributed += third_place_amount
                        logger.info(f"Distributed {third_place_amount} to third place user {third_place_user}")
                    else:
                        logger.error(f"Failed to distribute third place prize: {error}")
                
                # Mark contest as settled
                await settle_contest(session, contest_uuid)
                
                # Create audit log
                await create_audit_log(
                    session=session,
                    admin_id=None,  # System action
                    action="distribute_payouts",
                    resource_type="contest",
                    resource_id=contest_uuid,
                    details={
                        "contest_id": contest_id,
                        "total_entries": len(entries),
                        "total_prize_pool": str(prize_pool),
                        "total_commission": str(total_commission),
                        "total_distributed": str(total_distributed)
                    }
                )
                
                logger.info(f"Successfully distributed payouts for contest {contest_id}: {total_distributed} distributed")
                return True
        
        # Run async function in a separate thread with its own event loop
        import asyncio
        import threading
        import concurrent.futures
        
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_process())
            finally:
                loop.close()
                # Clean up any remaining tasks
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except:
                    pass
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_async)
            return future.result()
        
    except Exception as exc:
        logger.error(f"Error computing payouts for contest {contest_id}: {exc}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying payout computation for contest {contest_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))  # Exponential backoff
        else:
            logger.error(f"Max retries exceeded for contest {contest_id}")
            raise
