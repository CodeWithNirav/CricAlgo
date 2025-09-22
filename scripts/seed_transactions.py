#!/usr/bin/env python3
"""
Seed the database with sample transactions for testing
"""

import asyncio
import os
import sys
from decimal import Decimal
from datetime import datetime, timezone

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.admin import Admin
import uuid

async def seed_transactions():
    """Seed database with sample transactions"""
    async for db in get_db():
        try:
            print("🌱 Seeding transactions...")
            
            # Get a user to associate transactions with
            user_stmt = select(User).limit(1)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            
            if not user:
                print("❌ No users found. Please create a user first.")
                return
            
            print(f"📝 Using user: {user.username} (ID: {user.id})")
            
            # Get an admin for audit logs
            admin_stmt = select(Admin).limit(1)
            admin_result = await db.execute(admin_stmt)
            admin = admin_result.scalar_one_or_none()
            
            if not admin:
                print("❌ No admin found. Please create an admin first.")
                return
            
            print(f"👤 Using admin: {admin.username} (ID: {admin.id})")
            
            # Check if transactions already exist
            existing_stmt = select(Transaction).limit(1)
            existing_result = await db.execute(existing_stmt)
            existing = existing_result.scalar_one_or_none()
            
            if existing:
                print("✅ Transactions already exist, skipping seed")
                return
            
            # Create sample deposits
            deposits = [
                {
                    "user_id": user.id,
                    "tx_type": "deposit",
                    "amount": Decimal("100.0"),
                    "currency": "USDT",
                    "tx_metadata": {
                        "tx_hash": "0x1234567890abcdef1234567890abcdef12345678",
                        "telegram_id": str(user.telegram_id),
                        "username": user.username,
                        "network": "Ethereum",
                        "status": "pending"
                    }
                },
                {
                    "user_id": user.id,
                    "tx_type": "deposit",
                    "amount": Decimal("250.0"),
                    "currency": "USDT",
                    "tx_metadata": {
                        "tx_hash": "0xabcdef1234567890abcdef1234567890abcdef12",
                        "telegram_id": str(user.telegram_id),
                        "username": user.username,
                        "network": "Ethereum",
                        "status": "pending"
                    }
                },
                {
                    "user_id": user.id,
                    "tx_type": "deposit",
                    "amount": Decimal("50.0"),
                    "currency": "USDT",
                    "tx_metadata": {
                        "tx_hash": "0x9876543210fedcba9876543210fedcba98765432",
                        "telegram_id": str(user.telegram_id),
                        "username": user.username,
                        "network": "Ethereum",
                        "status": "confirmed"
                    }
                }
            ]
            
            # Create sample withdrawals
            withdrawals = [
                {
                    "user_id": user.id,
                    "tx_type": "withdrawal",
                    "amount": Decimal("75.0"),
                    "currency": "USDT",
                    "tx_metadata": {
                        "address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6",
                        "telegram_id": str(user.telegram_id),
                        "username": user.username,
                        "network": "Ethereum",
                        "status": "pending"
                    }
                },
                {
                    "user_id": user.id,
                    "tx_type": "withdrawal",
                    "amount": Decimal("125.0"),
                    "currency": "USDT",
                    "tx_metadata": {
                        "address": "0x8ba1f109551bD432803012645Hac136c4c8c8c8c",
                        "telegram_id": str(user.telegram_id),
                        "username": user.username,
                        "network": "Ethereum",
                        "status": "pending"
                    }
                }
            ]
            
            # Create transactions
            for deposit_data in deposits:
                transaction = Transaction(**deposit_data)
                db.add(transaction)
            
            for withdrawal_data in withdrawals:
                transaction = Transaction(**withdrawal_data)
                db.add(transaction)
            
            # Create some audit logs
            audit_logs = [
                {
                    "admin_id": admin.id,
                    "action": "system_startup",
                    "details": {"message": "System started successfully"}
                },
                {
                    "admin_id": admin.id,
                    "action": "seed_data",
                    "details": {"message": "Sample transactions created"}
                }
            ]
            
            for audit_data in audit_logs:
                audit_log = AuditLog(**audit_data)
                db.add(audit_log)
            
            await db.commit()
            
            print("✅ Successfully seeded:")
            print(f"   - {len(deposits)} deposits")
            print(f"   - {len(withdrawals)} withdrawals")
            print(f"   - {len(audit_logs)} audit logs")
            
        except Exception as e:
            print(f"❌ Error seeding transactions: {e}")
            await db.rollback()
        finally:
            await db.close()

if __name__ == "__main__":
    asyncio.run(seed_transactions())
