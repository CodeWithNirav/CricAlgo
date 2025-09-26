"""
Utility functions for calculating contest prizes after commission
"""

from decimal import Decimal
from typing import Dict, List, Optional, Union
from app.core.config import settings


def calculate_net_prize_pool(
    entry_fee: Decimal, 
    max_participants: int, 
    commission_pct: Optional[float] = None
) -> Decimal:
    """
    Calculate the net prize pool after deducting commission.
    Uses maximum participants to show the full potential prize pool.
    
    Args:
        entry_fee: Entry fee per participant
        max_participants: Maximum number of participants (not current count)
        commission_pct: Commission percentage (uses default if None)
    
    Returns:
        Net prize pool after commission deduction
    """
    if commission_pct is None:
        commission_pct = settings.platform_commission_pct
    
    total_entry_fees = entry_fee * max_participants
    commission = (total_entry_fees * Decimal(str(commission_pct)) / Decimal('100'))
    net_prize_pool = total_entry_fees - commission
    
    return net_prize_pool.quantize(Decimal('0.00000001'))


def calculate_prize_structure_payouts(
    prize_structure: List[Dict],
    net_prize_pool: Decimal
) -> List[Dict]:
    """
    Calculate actual payout amounts for each position in prize structure.
    
    Args:
        prize_structure: List of prize structure dictionaries with 'pos' and 'pct' keys
        net_prize_pool: Net prize pool after commission
    
    Returns:
        List of dictionaries with position, percentage, and actual payout amount
    """
    payouts = []
    
    for prize_slot in prize_structure:
        if not isinstance(prize_slot, dict):
            continue
            
        position = prize_slot.get("pos", 1)
        percentage = prize_slot.get("pct", 0)
        
        # Calculate actual payout amount
        payout_amount = (net_prize_pool * Decimal(str(percentage)) / Decimal('100')).quantize(Decimal('0.00000001'))
        
        payouts.append({
            "pos": position,
            "pct": percentage,
            "amount": payout_amount
        })
    
    return payouts


def format_prize_info(
    contest,
    max_participants: int,
    commission_pct: Optional[float] = None
) -> str:
    """
    Format prize information showing net amounts after commission.
    Uses maximum participants to show full potential prize pool.
    
    Args:
        contest: Contest object
        max_participants: Maximum number of participants (not current count)
        commission_pct: Commission percentage (uses contest or default if None)
    
    Returns:
        Formatted prize information string
    """
    if commission_pct is None:
        commission_pct = getattr(contest, 'commission_pct', None) or settings.platform_commission_pct
    
    # Calculate net prize pool using max participants
    net_prize_pool = calculate_net_prize_pool(
        Decimal(str(contest.entry_fee)), 
        max_participants, 
        commission_pct
    )
    
    # Handle prize structure
    if hasattr(contest, 'prize_structure') and contest.prize_structure:
        if isinstance(contest.prize_structure, list):
            # Calculate actual payouts
            payouts = calculate_prize_structure_payouts(contest.prize_structure, net_prize_pool)
            
            prize_info = f"🏆 *Prize Structure:*\n"
            for payout in payouts:
                prize_info += f"  Position {payout['pos']}: {payout['amount']} {contest.currency}\n"
        elif isinstance(contest.prize_structure, dict):
            prize_info = f"🏆 *Prize Structure:*\n"
            for position, amount in contest.prize_structure.items():
                # Convert percentage to actual amount
                if isinstance(amount, (int, float)) and amount <= 100:
                    actual_amount = (net_prize_pool * Decimal(str(amount)) / Decimal('100')).quantize(Decimal('0.00000001'))
                    prize_info += f"  {position}: {actual_amount} {contest.currency}\n"
                else:
                    prize_info += f"  {position}: {amount} {contest.currency}\n"
        else:
            prize_info = f"🏆 *Prize:* {contest.prize_structure} {contest.currency}\n"
    else:
        # Default: winner takes all (net amount)
        prize_info = f"🏆 *Prize:* Winner takes all ({net_prize_pool} {contest.currency})\n"
    
    return prize_info


def get_net_prize_pool_display(
    entry_fee: Union[Decimal, float, str],
    max_participants: int,
    commission_pct: Optional[float] = None
) -> str:
    """
    Get formatted net prize pool for display.
    Uses maximum participants to show full potential prize pool.
    
    Args:
        entry_fee: Entry fee per participant
        max_participants: Maximum number of participants (not current count)
        commission_pct: Commission percentage (uses default if None)
    
    Returns:
        Formatted net prize pool string
    """
    net_prize = calculate_net_prize_pool(
        Decimal(str(entry_fee)), 
        max_participants, 
        commission_pct
    )
    
    return f"{net_prize}"
