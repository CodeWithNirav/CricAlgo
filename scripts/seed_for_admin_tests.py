#!/usr/bin/env python3
"""
Seed script for admin tests
Creates sample data for testing the admin UI
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.db.session import get_db
from app.models.admin import Admin
from app.models.user import User
from app.models.invitation_code import InvitationCode
from app.models.match import Match
from app.models.contest import Contest
from app.models.contest_entry import ContestEntry
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.models.audit_log import AuditLog
from app.core.auth import get_password_hash
from sqlalchemy import select
import uuid


async def seed_admin_user(session):
    """Create a test admin user if SEED_ADMIN=true"""
    if not os.getenv("SEED_ADMIN", "false").lower() == "true":
        print("Skipping admin user creation (SEED_ADMIN not set)")
        return None
    
    # Check if admin already exists
    result = await session.execute(select(Admin).where(Admin.username == "ADMIN_SEED_USER"))
    existing_admin = result.scalar_one_or_none()
    
    if existing_admin:
        print("Admin user already exists")
        return existing_admin
    
    # Create admin user
    admin = Admin(
        username="ADMIN_SEED_USER",
        password_hash=get_password_hash("admin123"),
        email="admin@cricalgo.com",
        totp_secret=None  # No 2FA for test admin
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    
    print(f"Created admin user: {admin.username}")
    return admin


async def seed_invite_codes(session, admin_id):
    """Create sample invite codes"""
    # Check if invite codes already exist
    result = await session.execute(select(InvitationCode).limit(1))
    existing_codes = result.scalars().all()
    
    if existing_codes:
        print("Invite codes already exist")
        return
    
    # Create sample invite codes
    codes = [
        {
            "code": "WELCOME2024",
            "max_uses": 100,
            "expires_at": datetime.utcnow() + timedelta(days=30),
            "enabled": True
        },
        {
            "code": "VIP100",
            "max_uses": 10,
            "expires_at": datetime.utcnow() + timedelta(days=7),
            "enabled": True
        },
        {
            "code": "EXPIRED123",
            "max_uses": 50,
            "expires_at": datetime.utcnow() - timedelta(days=1),
            "enabled": False
        }
    ]
    
    for code_data in codes:
        invite_code = InvitationCode(
            code=code_data["code"],
            max_uses=code_data["max_uses"],
            expires_at=code_data["expires_at"],
            enabled=code_data["enabled"],
            created_by=admin_id
        )
        session.add(invite_code)
    
    await session.commit()
    print(f"Created {len(codes)} invite codes")


async def seed_sample_users(session):
    """Create sample users for testing"""
    # Check if users already exist
    result = await session.execute(select(User).limit(1))
    existing_users = result.scalars().all()
    
    if existing_users:
        print("Sample users already exist")
        return
    
    # Create sample users
    users = [
        {
            "telegram_id": 123456789,
            "username": "testuser1",
            "status": "ACTIVE"
        },
        {
            "telegram_id": 987654321,
            "username": "testuser2",
            "status": "FROZEN"
        },
        {
            "telegram_id": 555666777,
            "username": "testuser3",
            "status": "ACTIVE"
        }
    ]
    
    created_users = []
    for user_data in users:
        user = User(
            telegram_id=user_data["telegram_id"],
            username=user_data["username"],
            status=user_data["status"]
        )
        session.add(user)
        created_users.append(user)
    
    await session.commit()
    
    # Create wallets for users
    for user in created_users:
        wallet = Wallet(
            user_id=user.id,
            deposit_balance=Decimal("100.00"),
            winning_balance=Decimal("50.00"),
            bonus_balance=Decimal("25.00")
        )
        session.add(wallet)
    
    await session.commit()
    print(f"Created {len(users)} sample users with wallets")


async def seed_sample_match_and_contest(session):
    """Create a sample match and contest for E2E testing"""
    # Check if matches already exist
    result = await session.execute(select(Match).limit(1))
    existing_matches = result.scalars().all()
    
    if existing_matches:
        print("Sample matches already exist")
        return
    
    # Create sample match
    match = Match(
        title="India vs Australia - Test Match",
        start_time=datetime.utcnow() + timedelta(hours=2),
        external_id="IND-AUS-2024-001"
    )
    session.add(match)
    await session.commit()
    await session.refresh(match)
    
    # Create sample contest
    contest = Contest(
        match_id=match.id,
        code="IND-AUS-HIGH-ROLLER",
        title="High Roller Contest",
        entry_fee=Decimal("10.00"),
        currency="USDT",
        max_players=100,
        prize_structure={
            "1st": "50%",
            "2nd": "30%",
            "3rd": "20%"
        },
        commission_pct=Decimal("5.00"),
        join_cutoff=datetime.utcnow() + timedelta(hours=1),
        status="open"
    )
    session.add(contest)
    await session.commit()
    await session.refresh(contest)
    
    # Create sample contest entries
    users_result = await session.execute(select(User).limit(2))
    users = users_result.scalars().all()
    
    for i, user in enumerate(users):
        entry = ContestEntry(
            contest_id=contest.id,
            user_id=user.id,
            entry_code=f"ENTRY-{contest.code}-{i+1:03d}",
            amount_debited=contest.entry_fee
        )
        session.add(entry)
    
    await session.commit()
    print(f"Created sample match '{match.title}' and contest '{contest.title}' with {len(users)} entries")


async def seed_sample_transactions(session):
    """Create sample transactions for testing"""
    # Check if transactions already exist
    result = await session.execute(select(Transaction).limit(1))
    existing_transactions = result.scalars().all()
    
    if existing_transactions:
        print("Sample transactions already exist")
        return
    
    # Get a sample user
    users_result = await session.execute(select(User).limit(1))
    user = users_result.scalar_one_or_none()
    
    if not user:
        print("No users found, skipping transaction creation")
        return
    
    # Create sample transactions
    transactions = [
        {
            "user_id": user.id,
            "tx_type": "deposit",
            "amount": Decimal("100.00"),
            "currency": "USDT",
            "related_entity": "bep20",
            "tx_metadata": {"tx_hash": "0x1234567890abcdef", "status": "pending"}
        },
        {
            "user_id": user.id,
            "tx_type": "withdrawal",
            "amount": Decimal("50.00"),
            "currency": "USDT",
            "related_entity": "bep20",
            "tx_metadata": {"tx_hash": "0xabcdef1234567890", "status": "pending"}
        }
    ]
    
    for tx_data in transactions:
        transaction = Transaction(**tx_data)
        session.add(transaction)
    
    await session.commit()
    print(f"Created {len(transactions)} sample transactions")


async def main():
    """Main seeding function"""
    print("Starting admin test data seeding...")
    
    async for session in get_db():
        try:
            # Seed admin user
            admin = await seed_admin_user(session)
            
            # Seed invite codes
            if admin:
                await seed_invite_codes(session, admin.id)
            
            # Seed sample users
            await seed_sample_users(session)
            
            # Seed sample match and contest
            await seed_sample_match_and_contest(session)
            
            # Seed sample transactions
            await seed_sample_transactions(session)
            
            print("Admin test data seeding completed successfully!")
            
        except Exception as e:
            print(f"Error during seeding: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()
        break


if __name__ == "__main__":
    asyncio.run(main())
