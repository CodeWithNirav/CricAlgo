"""
Contest settlement service for deterministic payout distribution
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from sqlalchemy.orm import selectinload

from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.models.enums import ContestStatus
from app.core.config import settings
from app.repos.wallet_repo import credit_winning_atomic
from app.repos.audit_log_repo import create_audit_log

# Configure logging
logger = logging.getLogger(__name__)

# Decimal precision for calculations
DECIMAL_PRECISION = Decimal("0.00000001")


async def settle_contest(
    session: AsyncSession, 
    contest_id: UUID, 
    admin_id: Optional[UUID] = None
) -> Dict:
    """
    Settle a contest with deterministic payout distribution.
    
    This function is atomic and idempotent - it can be called multiple times
    safely without double-paying winners.
    
    Args:
        session: Database session
        contest_id: Contest UUID to settle
        admin_id: Admin UUID who initiated settlement (optional)
    
    Returns:
        Dict containing settlement summary with payouts, commission, etc.
    """
    logger.info(f"Starting settlement for contest {contest_id}")
    
    try:
        async with session.begin():
            # Step 1: Lock contest row for update to prevent concurrent settlements
            contest_result = await session.execute(
                select(Contest)
                .where(Contest.id == contest_id)
                .with_for_update()
            )
            contest = contest_result.scalar_one_or_none()
            
            if not contest:
                raise ValueError(f"Contest {contest_id} not found")
            
            # Step 2: Check if already settled or cancelled (idempotency)
            if contest.status in (ContestStatus.SETTLED, ContestStatus.CANCELLED):
                logger.info(f"Contest {contest_id} already {contest.status.value}, returning existing result")
                return await _get_existing_settlement_result(session, contest_id)
            
            # Step 3: Load all contest entries ordered by creation time (deterministic)
            entries_result = await session.execute(
                select(ContestEntry)
                .where(ContestEntry.contest_id == contest_id)
                .order_by(ContestEntry.created_at)
            )
            entries = entries_result.scalars().all()
            
            if not entries:
                raise ValueError(f"No entries found for contest {contest_id}")
            
            num_players = len(entries)
            logger.info(f"Found {num_players} entries for contest {contest_id}")
            
            # Step 4: Compute total prize pool and commission
            total_prize_pool = contest.entry_fee * num_players
            commission_pct = contest.commission_pct or settings.platform_commission_pct
            commission = (total_prize_pool * Decimal(str(commission_pct)) / Decimal('100')).quantize(DECIMAL_PRECISION)
            distributable_pool = (total_prize_pool - commission).quantize(DECIMAL_PRECISION)
            
            logger.info(f"Prize pool: {total_prize_pool}, Commission: {commission}, Distributable: {distributable_pool}")
            
            # Step 5: Parse prize structure and compute payouts
            prize_structure = contest.prize_structure or []
            if not prize_structure:
                # Default to winner-takes-all if no prize structure
                prize_structure = [{"pos": 1, "pct": 100}]
            
            payouts = []
            total_payouts = Decimal('0')
            
            for prize_slot in prize_structure:
                position = prize_slot.get("pos", 1)
                percentage = prize_slot.get("pct", 0)
                
                # Skip if position is beyond number of players
                if position > num_players:
                    continue
                
                # Calculate payout amount
                payout_amount = (distributable_pool * Decimal(str(percentage)) / Decimal('100')).quantize(DECIMAL_PRECISION)
                
                if payout_amount > 0 and position <= len(entries):
                    # Get the entry for this position (0-indexed)
                    entry = entries[position - 1]
                    
                    # Step 6: Credit winning balance atomically
                    success, error_msg, new_balance = await credit_winning_atomic(
                        session=session,
                        user_id=entry.user_id,
                        amount=payout_amount,
                        reason="contest_payout",
                        meta={
                            "contest_id": str(contest_id),
                            "entry_id": str(entry.id),
                            "position": position,
                            "percentage": percentage,
                            "idempotency_key": f"contest_{contest_id}_entry_{entry.id}_payout"
                        }
                    )
                    
                    if not success:
                        raise RuntimeError(f"Failed to credit payout for user {entry.user_id}: {error_msg}")
                    
                    # Create transaction record
                    transaction = Transaction(
                        user_id=entry.user_id,
                        tx_type="internal",
                        amount=payout_amount,
                        currency=contest.currency,
                        related_entity="contest",
                        related_id=contest_id,
                        tx_metadata={
                            "contest_id": str(contest_id),
                            "entry_id": str(entry.id),
                            "position": position,
                            "percentage": percentage,
                            "payout_type": "contest_winning"
                        },
                        processed_at=datetime.utcnow()
                    )
                    session.add(transaction)
                    
                    payouts.append({
                        "user_id": str(entry.user_id),
                        "entry_id": str(entry.id),
                        "position": position,
                        "amount": str(payout_amount),
                        "percentage": percentage,
                        "new_balance": str(new_balance)
                    })
                    
                    total_payouts += payout_amount
                    
                    logger.info(f"Credited {payout_amount} to user {entry.user_id} (position {position})")
            
            # Step 7: Record audit log
            settlement_details = {
                "contest_id": str(contest_id),
                "num_players": num_players,
                "total_prize_pool": str(total_prize_pool),
                "commission_pct": commission_pct,
                "commission_amount": str(commission),
                "distributable_pool": str(distributable_pool),
                "total_payouts": str(total_payouts),
                "payouts": payouts,
                "prize_structure": prize_structure
            }
            
            audit_log = AuditLog(
                admin_id=admin_id,
                action="contest_settlement",
                details=settlement_details
            )
            session.add(audit_log)
            
            # Step 8: Mark contest as settled
            contest.status = ContestStatus.SETTLED
            contest.settled_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"Successfully settled contest {contest_id} with {len(payouts)} payouts totaling {total_payouts}")
            
            return {
                "success": True,
                "contest_id": str(contest_id),
                "settlement_time": contest.settled_at.isoformat(),
                "num_players": num_players,
                "total_prize_pool": str(total_prize_pool),
                "commission_pct": commission_pct,
                "commission_amount": str(commission),
                "distributable_pool": str(distributable_pool),
                "total_payouts": str(total_payouts),
                "payouts": payouts,
                "prize_structure": prize_structure
            }
            
    except Exception as e:
        logger.error(f"Error settling contest {contest_id}: {str(e)}")
        await session.rollback()
        raise


async def _get_existing_settlement_result(session: AsyncSession, contest_id: UUID) -> Dict:
    """
    Get existing settlement result for already settled contest.
    
    Args:
        session: Database session
        contest_id: Contest UUID
    
    Returns:
        Dict containing existing settlement details
    """
    # Get the contest
    contest_result = await session.execute(
        select(Contest).where(Contest.id == contest_id)
    )
    contest = contest_result.scalar_one_or_none()
    
    if not contest:
        raise ValueError(f"Contest {contest_id} not found")
    
    # Get audit log for this settlement
    audit_result = await session.execute(
        select(AuditLog)
        .where(AuditLog.action == "contest_settlement")
        .where(AuditLog.details["contest_id"].astext == str(contest_id))
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    audit_log = audit_result.scalar_one_or_none()
    
    if audit_log and audit_log.details:
        return {
            "success": True,
            "contest_id": str(contest_id),
            "settlement_time": contest.settled_at.isoformat() if contest.settled_at else None,
            "status": "already_settled",
            **audit_log.details
        }
    else:
        # Fallback if no audit log found
        return {
            "success": True,
            "contest_id": str(contest_id),
            "settlement_time": contest.settled_at.isoformat() if contest.settled_at else None,
            "status": "already_settled",
            "message": "Contest was previously settled but audit details not found"
        }
