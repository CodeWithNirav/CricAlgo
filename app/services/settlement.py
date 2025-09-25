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


async def _settle_contest_inner(
    session: AsyncSession, 
    contest_id: UUID, 
    admin_id: Optional[UUID] = None
) -> Dict:
    """
    Inner settlement function that does the actual work.
    """
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
    if contest.status in ('closed', 'cancelled'):
        logger.info(f"Contest {contest_id} already {contest.status}, returning existing result")
        return await _get_existing_settlement_result(session, contest_id)
    
    # Step 3: Load all contest entries ordered by winner rank (admin-selected winners first)
    entries_result = await session.execute(
        select(ContestEntry)
        .where(ContestEntry.contest_id == contest_id)
        .order_by(ContestEntry.winner_rank.asc().nulls_last(), ContestEntry.created_at)
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
    
    # Handle case where prize_structure might be a JSON string
    if isinstance(prize_structure, str):
        try:
            import json
            prize_structure = json.loads(prize_structure)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Invalid prize structure format: {prize_structure}")
            prize_structure = []
    
    # Handle different prize structure formats
    if isinstance(prize_structure, dict):
        # Convert dict format to list format
        prize_structure = [{"pos": int(k), "pct": v * 100 if v <= 1 else v} for k, v in prize_structure.items()]
    
    if not prize_structure:
        # Default to winner-takes-all if no prize structure
        prize_structure = [{"pos": 1, "pct": 100}]
    
    logger.info(f"Prize structure: {prize_structure}, type: {type(prize_structure)}")
    
    # Validate that prize structure percentages add up to 100%
    total_percentage = sum(item.get("pct", 0) for item in prize_structure if isinstance(item, dict))
    if abs(total_percentage - 100) > 0.01:  # Allow small floating point errors
        logger.warning(f"Prize structure percentages don't add up to 100%: {total_percentage}%")
        # Normalize to 100% if close enough
        if total_percentage > 0:
            for item in prize_structure:
                if isinstance(item, dict):
                    item["pct"] = (item.get("pct", 0) / total_percentage) * 100
    
    payouts = []
    total_payouts = Decimal('0')
    
    # Get entries with winner ranks (admin-selected winners)
    ranked_entries = [e for e in entries if e.winner_rank is not None]
    ranked_entries.sort(key=lambda x: x.winner_rank)
    
    logger.info(f"Found {len(ranked_entries)} ranked entries out of {len(entries)} total entries")
    
    # Validate that winners have been selected
    if not ranked_entries:
        raise ValueError("No winners have been selected for this contest. Please select winners before settling.")
    
    for prize_slot in prize_structure:
        logger.info(f"Processing prize slot: {prize_slot}, type: {type(prize_slot)}")
        if not isinstance(prize_slot, dict):
            logger.warning(f"Invalid prize slot format: {prize_slot}")
            continue
            
        position = prize_slot.get("pos", 1)
        percentage = prize_slot.get("pct", 0)
        
        # Skip if position is beyond number of ranked entries
        if position > len(ranked_entries):
            logger.warning(f"Position {position} exceeds number of ranked entries ({len(ranked_entries)}) - skipping this prize slot")
            continue
        
        # Calculate payout amount
        payout_amount = (distributable_pool * Decimal(str(percentage)) / Decimal('100')).quantize(DECIMAL_PRECISION)
        
        if payout_amount > 0:
            # Get the entry at the specified position (1-indexed)
            entry = ranked_entries[position - 1] if position <= len(ranked_entries) else None
            
            if not entry:
                logger.warning(f"No entry found for position {position}")
                continue
            
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
                }
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
    
    # Verify that total payouts don't exceed distributable pool
    if total_payouts > distributable_pool:
        logger.error(f"Total payouts ({total_payouts}) exceed distributable pool ({distributable_pool})")
        raise RuntimeError("Total payouts exceed available distributable pool")
    
    # Step 7: Record audit log
    settlement_details = {
        "contest_id": str(contest_id),
        "num_players": num_players,
        "total_prize_pool": str(total_prize_pool),
        "commission_pct": float(commission_pct),  # Convert Decimal to float for JSON serialization
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
    
    # Step 8: Mark contest as closed (settled)
    contest.status = 'closed'
    
    logger.info(f"Successfully settled contest {contest_id} with {len(payouts)} payouts totaling {total_payouts}")
    
    # Log detailed settlement information
    logger.info(f"Settlement summary:")
    logger.info(f"  - Contest ID: {contest_id}")
    logger.info(f"  - Total entries: {num_players}")
    logger.info(f"  - Ranked entries: {len(ranked_entries)}")
    logger.info(f"  - Total prize pool: {total_prize_pool}")
    logger.info(f"  - Commission: {commission}")
    logger.info(f"  - Distributable pool: {distributable_pool}")
    logger.info(f"  - Total payouts: {total_payouts}")
    logger.info(f"  - Number of payouts: {len(payouts)}")
    
    for payout in payouts:
        logger.info(f"    - Position {payout['position']}: {payout['amount']} to user {payout['user_id']}")
    
    # Skip notifications for now to avoid transaction rollback issues
    # TODO: Fix notification system to work with missing chat_map table
    logger.info(f"Skipping settlement notifications for contest {contest_id} (notifications disabled)")
    
    return {
        "success": True,
        "contest_id": str(contest_id),
        "settlement_time": datetime.utcnow().isoformat(),
        "num_players": num_players,
        "total_prize_pool": str(total_prize_pool),
        "commission_pct": commission_pct,
        "commission_amount": str(commission),
        "distributable_pool": str(distributable_pool),
        "total_payouts": str(total_payouts),
        "payouts": payouts,
        "prize_structure": prize_structure
    }


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
        # Check if session already has a transaction
        if session.in_transaction():
            # Use existing transaction
            return await _settle_contest_inner(session, contest_id, admin_id)
        else:
            # Start new transaction
            async with session.begin():
                return await _settle_contest_inner(session, contest_id, admin_id)
            
    except Exception as e:
        logger.error(f"Error settling contest {contest_id}: {str(e)}")
        await session.rollback()
        return {
            "success": False,
            "error": str(e),
            "contest_id": str(contest_id)
        }


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
        logger.info(f"Audit log details type: {type(audit_log.details)}, value: {audit_log.details}")
        if isinstance(audit_log.details, dict):
            return {
                "success": True,
                "contest_id": str(contest_id),
                "settlement_time": contest.settled_at.isoformat() if contest.settled_at else None,
                "status": "already_settled",
                **audit_log.details
            }
        else:
            # If details is not a dict, return it as a string
            return {
                "success": True,
                "contest_id": str(contest_id),
                "settlement_time": contest.settled_at.isoformat() if contest.settled_at else None,
                "status": "already_settled",
                "details": str(audit_log.details)
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
