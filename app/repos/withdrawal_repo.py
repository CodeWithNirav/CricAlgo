import uuid
from app.models.withdrawal import Withdrawal
from sqlalchemy import select

async def create_withdrawal(db, telegram_id, amount, address):
    """Create a withdrawal request"""
    withdrawal_id = str(uuid.uuid4())
    w = Withdrawal(
        id=withdrawal_id,
        telegram_id=str(telegram_id),
        amount=str(amount),
        address=address,
        status='pending'
    )
    db.add(w)
    await db.flush()
    return {
        "id": w.id,
        "telegram_id": w.telegram_id,
        "amount": w.amount,
        "address": w.address,
        "status": w.status
    }

async def get_withdrawal(db, withdrawal_id):
    """Get a withdrawal by ID"""
    result = await db.execute(select(Withdrawal).where(Withdrawal.id == withdrawal_id))
    return result.scalar_one_or_none()

async def approve_withdrawal(db, withdrawal_id):
    """Approve a withdrawal"""
    w = await get_withdrawal(db, withdrawal_id)
    if not w:
        return False
    w.status = 'approved'
    await db.flush()
    return True


async def get_withdrawal_by_id(session, withdrawal_id):
    """Get withdrawal by ID - alias for compatibility"""
    return await get_withdrawal(session, withdrawal_id)