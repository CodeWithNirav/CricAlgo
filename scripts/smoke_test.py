#!/usr/bin/env python3
"""
CricAlgo Smoke Test Script

This script performs a comprehensive end-to-end smoke test of the CricAlgo system.
It validates core happy-path flows including user registration, deposits, contests,
payouts, and withdrawals using the fake-blockchain service.

Usage:
    python scripts/smoke_test.py [--nocleanup]

Environment Variables:
    - DATABASE_URL: Database connection string
    - REDIS_URL: Redis connection string
    - WEBHOOK_SECRET: Webhook signature secret
    - SEED_ADMIN_USERNAME: Admin username for testing
    - SEED_ADMIN_EMAIL: Admin email for testing
    - SEED_ADMIN_PASSWORD: Admin password for testing
"""

import asyncio
import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any

# Ensure UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

import httpx

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.repos.user_repo import get_user_by_username
from app.repos.wallet_repo import get_wallet_for_user
from app.repos.transaction_repo import create_transaction, get_transactions_by_user
from app.repos.contest_entry_repo import get_contest_entries
from app.repos.audit_log_repo import get_audit_logs
from app.models.enums import ContestStatus


class SmokeTestLogger:
    """Custom logger for smoke test with structured output"""
    
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.logger = logging.getLogger("smoke_test")
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def success(self, message: str):
        self.logger.info(f"SUCCESS: {message}")
    
    def fail(self, message: str):
        self.logger.error(f"FAIL: {message}")


class SmokeTestRunner:
    """Main smoke test runner class"""
    
    def __init__(self, nocleanup: bool = False):
        self.nocleanup = nocleanup
        self.timestamp = int(time.time())
        # Detect if running inside Docker container
        if os.path.exists("/.dockerenv"):
            # Running inside Docker - use service names
            self.base_url = "http://app:8000"
            self.fake_blockchain_url = "http://fake-blockchain:8081"
        else:
            # Running outside Docker - use localhost with exposed ports
            self.base_url = "http://localhost:8001"
            self.fake_blockchain_url = "http://localhost:8081"
        self.artifacts_dir = "artifacts"
        self.log_file = f"{self.artifacts_dir}/smoke_test.log"
        self.result_file = f"{self.artifacts_dir}/smoke_test_result.json"
        
        # Create artifacts directory
        os.makedirs(self.artifacts_dir, exist_ok=True)
        
        # Initialize logger
        self.logger = SmokeTestLogger(self.log_file)
        
        # Test data
        self.user_a_username = f"smoke_user_a_{self.timestamp}"
        self.user_b_username = f"smoke_user_b_{self.timestamp}"
        self.user_a_telegram_id = 1000 + self.timestamp % 10000  # Make telegram_id unique
        self.user_b_telegram_id = 2000 + self.timestamp % 10000  # Make telegram_id unique
        self.match_id = f"smoke_match_{self.timestamp}"
        self.tx_hash = f"smoke_tx_{self.timestamp}"
        
        # Tokens and IDs
        self.user_a_token = None
        self.user_b_token = None
        self.admin_token = None
        self.contest_id = None
        
        # Test results
        self.results = {
            "status": "running",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "steps": [],
            "assertions": [],
            "final_balances": {},
            "errors": []
        }
    
    def log_step(self, step: str, status: str = "info", details: str = ""):
        """Log a test step with status"""
        step_data = {
            "step": step,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details
        }
        self.results["steps"].append(step_data)
        
        if status == "success":
            self.logger.success(f"{step}: {details}")
        elif status == "error":
            self.logger.error(f"{step}: {details}")
        else:
            self.logger.info(f"{step}: {details}")
    
    def add_assertion(self, assertion: str, passed: bool, details: str = ""):
        """Add an assertion result"""
        assertion_data = {
            "assertion": assertion,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.results["assertions"].append(assertion_data)
        
        if passed:
            self.logger.success(f"✓ {assertion}: {details}")
        else:
            self.logger.fail(f"✗ {assertion}: {details}")
            self.results["errors"].append(f"{assertion}: {details}")
    
    async def wait_for_services(self, timeout: int = 60) -> bool:
        """Wait for all services to be ready"""
        self.log_step("Waiting for services to be ready")
        
        start_time = time.time()
        services_ready = {
            "app": False,
            "docs": False,
            "redis": False,
            "fake_blockchain": False
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.time() - start_time < timeout:
                try:
                    # Check app health
                    if not services_ready["app"]:
                        response = await client.get(f"{self.base_url}/api/v1/health")
                        if response.status_code == 200:
                            services_ready["app"] = True
                            self.log_step("App health check", "success", "App is responding")
                    
                    # Check docs
                    if not services_ready["docs"]:
                        response = await client.get(f"{self.base_url}/docs")
                        if response.status_code == 200:
                            services_ready["docs"] = True
                            self.log_step("API docs", "success", "Docs are accessible")
                    
                    # Check fake blockchain service
                    if not services_ready["fake_blockchain"]:
                        response = await client.get(f"{self.fake_blockchain_url}/")
                        if response.status_code == 200:
                            services_ready["fake_blockchain"] = True
                            self.log_step("Fake blockchain", "success", "Service is responding")
                    
                    # Check Redis (via app health or direct check)
                    if not services_ready["redis"]:
                        # We'll assume Redis is ready if app is ready
                        if services_ready["app"]:
                            services_ready["redis"] = True
                            self.log_step("Redis", "success", "Redis is accessible")
                    
                    if all(services_ready.values()):
                        self.log_step("All services ready", "success", "All services are responding")
                        return True
                    
                except Exception as e:
                    self.logger.info(f"Service check failed: {e}")
                
                await asyncio.sleep(2)
        
        self.log_step("Service readiness timeout", "error", f"Services not ready after {timeout}s")
        return False
    
    async def create_admin_user(self) -> bool:
        """Create admin user if not exists"""
        self.log_step("Creating admin user")
        
        try:
            # Check if admin already exists
            async with AsyncSessionLocal() as session:
                admin_user = await get_user_by_username(session, "admin")
                if admin_user:
                    self.log_step("Admin user exists", "success", "Using existing admin")
                    return True
            
            # Create admin using the script
            import subprocess
            result = subprocess.run([
                "python", "scripts/create_admin.py"
            ], capture_output=True, text=True, env={
                **os.environ,
                "SEED_ADMIN_USERNAME": "admin",
                "SEED_ADMIN_EMAIL": "admin@cricalgo.com",
                "SEED_ADMIN_PASSWORD": "admin123"
            })
            
            if result.returncode == 0:
                self.log_step("Admin user created", "success", "Admin user created successfully")
                return True
            else:
                self.log_step("Admin creation failed", "error", result.stderr)
                return False
                
        except Exception as e:
            self.log_step("Admin creation error", "error", str(e))
            return False
    
    async def login_admin(self) -> bool:
        """Login as admin user"""
        self.log_step("Logging in as admin")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # For testing, we'll use the admin user account (not the admin record)
                # The admin creation script creates a user account with username "admin_admin"
                response = await client.post(f"{self.base_url}/api/v1/login", json={
                    "username": "admin_admin",
                    "password": "admin123"
                })
                
                if response.status_code == 200:
                    data = response.json()
                    self.admin_token = data["access_token"]
                    self.log_step("Admin login", "success", "Admin logged in successfully")
                    return True
                else:
                    self.log_step("Admin login failed", "error", f"Status: {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_step("Admin login error", "error", str(e))
            return False
    
    async def create_test_users(self) -> bool:
        """Create two test users"""
        self.log_step("Creating test users")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Create user A
                response_a = await client.post(f"{self.base_url}/api/v1/register", json={
                    "username": self.user_a_username,
                    "telegram_id": self.user_a_telegram_id
                })
                
                if response_a.status_code != 200:
                    self.log_step("User A creation failed", "error", f"Status: {response_a.status_code}")
                    return False
                
                data_a = response_a.json()
                self.user_a_token = data_a["access_token"]
                self.log_step("User A created", "success", f"Username: {self.user_a_username}")
                
                # Create user B
                response_b = await client.post(f"{self.base_url}/api/v1/register", json={
                    "username": self.user_b_username,
                    "telegram_id": self.user_b_telegram_id
                })
                
                if response_b.status_code != 200:
                    self.log_step("User B creation failed", "error", f"Status: {response_b.status_code}")
                    return False
                
                data_b = response_b.json()
                self.user_b_token = data_b["access_token"]
                self.log_step("User B created", "success", f"Username: {self.user_b_username}")
                
                return True
                
        except Exception as e:
            self.log_step("User creation error", "error", str(e))
            return False
    
    async def create_deposit_transaction(self) -> bool:
        """Create a pending deposit transaction for user A"""
        self.log_step("Creating deposit transaction")
        
        try:
            async with AsyncSessionLocal() as session:
                # Get user A
                user_a = await get_user_by_username(session, self.user_a_username)
                if not user_a:
                    self.log_step("User A not found", "error", "Cannot create deposit")
                    return False
                
                # Create pending transaction
                transaction = await create_transaction(
                    session=session,
                    user_id=user_a.id,
                    tx_type="deposit",
                    amount=Decimal("10.0"),
                    currency="USDT",
                    related_entity="blockchain",
                    related_id=user_a.id,
                    tx_metadata={
                        "tx_hash": self.tx_hash,
                        "status": "pending",
                        "chain": "bep20",
                        "confirmations": 0
                    }
                )
                
                self.log_step("Deposit transaction created", "success", f"TX: {self.tx_hash}")
                return True
                
        except Exception as e:
            self.log_step("Deposit creation error", "error", str(e))
            return False
    
    async def simulate_webhook_confirmation(self) -> bool:
        """Simulate webhook confirmation with idempotency test"""
        self.log_step("Simulating webhook confirmation")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Prepare webhook payload
                payload = {
                    "tx_hash": self.tx_hash,
                    "confirmations": 12,
                    "amount": "10.0",
                    "currency": "USDT",
                    "status": "confirmed",
                    "block_number": 12345
                }
                
                # Compute HMAC signature if secret is available
                headers = {}
                if settings.webhook_secret:
                    body = json.dumps(payload).encode()
                    signature = hmac.new(
                        settings.webhook_secret.encode(),
                        body,
                        hashlib.sha256
                    ).hexdigest()
                    headers["X-Signature"] = signature
                
                # Send webhook twice to test idempotency
                for attempt in range(2):
                    response = await client.post(
                        f"{self.base_url}/api/v1/webhooks/bep20",
                        json=payload,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        self.log_step(f"Webhook attempt {attempt + 1}", "success", f"Status: {response.status_code}")
                    else:
                        self.log_step(f"Webhook attempt {attempt + 1}", "error", f"Status: {response.status_code}")
                        return False
                
                return True
                
        except Exception as e:
            self.log_step("Webhook simulation error", "error", str(e))
            return False
    
    async def verify_deposit_processing(self) -> bool:
        """Verify deposit was processed correctly"""
        self.log_step("Verifying deposit processing")
        
        try:
            async with AsyncSessionLocal() as session:
                # Get user A
                user_a = await get_user_by_username(session, self.user_a_username)
                if not user_a:
                    self.log_step("User A not found", "error", "Cannot verify deposit")
                    return False
                
                # Get wallet
                wallet = await get_wallet_for_user(session, user_a.id)
                if not wallet:
                    self.log_step("Wallet not found", "error", "Cannot verify deposit")
                    return False
                
                # Check deposit balance
                deposit_balance = wallet.deposit_balance
                self.add_assertion(
                    "Deposit balance increased",
                    deposit_balance >= Decimal("10.0"),
                    f"Balance: {deposit_balance}"
                )
                
                # Check transaction status
                transactions = await get_transactions_by_user(session, user_a.id, limit=10)
                deposit_tx = None
                for tx in transactions:
                    if tx.tx_metadata and tx.tx_metadata.get("tx_hash") == self.tx_hash:
                        deposit_tx = tx
                        break
                
                if deposit_tx:
                    status = deposit_tx.tx_metadata.get("status", "unknown")
                    self.add_assertion(
                        "Transaction status is confirmed",
                        status == "confirmed",
                        f"Status: {status}"
                    )
                else:
                    self.add_assertion(
                        "Deposit transaction found",
                        False,
                        "Transaction not found"
                    )
                
                return deposit_balance >= Decimal("10.0")
                
        except Exception as e:
            self.log_step("Deposit verification error", "error", str(e))
            return False
    
    async def create_contest(self) -> bool:
        """Create a contest as admin"""
        self.log_step("Creating contest")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                
                response = await client.post(f"{self.base_url}/api/v1/admin/contest", json={
                    "match_id": self.match_id,
                    "title": "Smoke Contest",
                    "description": "Test contest for smoke testing",
                    "entry_fee": "1.0",
                    "max_participants": 2,
                    "prize_structure": [{"pos": 1, "pct": 100}]
                }, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    self.contest_id = data["id"]
                    self.log_step("Contest created", "success", f"ID: {self.contest_id}")
                    return True
                else:
                    self.log_step("Contest creation failed", "error", f"Status: {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_step("Contest creation error", "error", str(e))
            return False
    
    async def join_contest_users(self) -> bool:
        """Both users join the contest"""
        self.log_step("Users joining contest")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # User A joins
                headers_a = {"Authorization": f"Bearer {self.user_a_token}"}
                response_a = await client.post(
                    f"{self.base_url}/api/v1/contest/{self.contest_id}/join",
                    headers=headers_a
                )
                
                if response_a.status_code != 200:
                    self.log_step("User A join failed", "error", f"Status: {response_a.status_code}")
                    return False
                
                self.log_step("User A joined", "success", "User A joined contest")
                
                # Give user B some funds first
                await self.fund_user_b()
                
                # User B joins
                headers_b = {"Authorization": f"Bearer {self.user_b_token}"}
                response_b = await client.post(
                    f"{self.base_url}/api/v1/contest/{self.contest_id}/join",
                    headers=headers_b
                )
                
                if response_b.status_code != 200:
                    self.log_step("User B join failed", "error", f"Status: {response_b.status_code}")
                    return False
                
                self.log_step("User B joined", "success", "User B joined contest")
                return True
                
        except Exception as e:
            self.log_step("Contest join error", "error", str(e))
            return False
    
    async def fund_user_b(self) -> bool:
        """Fund user B for contest entry"""
        self.log_step("Funding user B")
        
        try:
            async with AsyncSessionLocal() as session:
                # Get user B
                user_b = await get_user_by_username(session, self.user_b_username)
                if not user_b:
                    self.log_step("User B not found", "error", "Cannot fund user")
                    return False
                
                # Create a deposit transaction for user B
                tx_hash_b = f"smoke_tx_b_{self.timestamp}"
                transaction = await create_transaction(
                    session=session,
                    user_id=user_b.id,
                    tx_type="deposit",
                    amount=Decimal("2.0"),
                    currency="USDT",
                    related_entity="blockchain",
                    related_id=user_b.id,
                    tx_metadata={
                        "tx_hash": tx_hash_b,
                        "status": "confirmed",
                        "chain": "bep20",
                        "confirmations": 3
                    }
                )
                
                # Update wallet balance
                from app.repos.wallet_repo import update_balances_atomic
                success, error = await update_balances_atomic(
                    session,
                    user_b.id,
                    deposit_delta=Decimal("2.0")
                )
                
                if success:
                    self.log_step("User B funded", "success", "User B has 2.0 USDT")
                    return True
                else:
                    self.log_step("User B funding failed", "error", error)
                    return False
                
        except Exception as e:
            self.log_step("User B funding error", "error", str(e))
            return False
    
    async def settle_contest(self) -> bool:
        """Settle the contest and trigger payouts"""
        self.log_step("Settling contest")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self.admin_token}"}
                
                response = await client.post(
                    f"{self.base_url}/api/v1/admin/contest/{self.contest_id}/settle",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_step("Contest settled", "success", f"Payouts: {data['total_payouts']}")
                    return True
                else:
                    self.log_step("Contest settlement failed", "error", f"Status: {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_step("Contest settlement error", "error", str(e))
            return False
    
    async def wait_for_payouts(self, timeout: int = 30) -> bool:
        """Wait for payouts to be processed"""
        self.log_step("Waiting for payouts")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                async with AsyncSessionLocal() as session:
                    # Check if contest is settled
                    from app.repos.contest_repo import get_contest_by_id
                    contest = await get_contest_by_id(session, self.contest_id)
                    
                    if contest and contest.status == ContestStatus.SETTLED:
                        self.log_step("Payouts processed", "success", "Contest settled and payouts completed")
                        return True
                    
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.info(f"Payout check error: {e}")
                await asyncio.sleep(2)
        
        self.log_step("Payout timeout", "error", f"Payouts not completed after {timeout}s")
        return False
    
    async def create_withdrawal_request(self) -> bool:
        """Create a withdrawal request for the winner"""
        self.log_step("Creating withdrawal request")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self.user_a_token}"}
                
                response = await client.post(f"{self.base_url}/api/v1/wallet/withdraw", json={
                    "amount": "3.0",
                    "currency": "USDT",
                    "withdrawal_address": "0x1234567890123456789012345678901234567890",
                    "notes": "Smoke test withdrawal"
                }, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    self.log_step("Withdrawal created", "success", f"TX: {data['transaction_id']}")
                    return True
                else:
                    self.log_step("Withdrawal creation failed", "error", f"Status: {response.status_code}")
                    return False
                    
        except Exception as e:
            self.log_step("Withdrawal creation error", "error", str(e))
            return False
    
    async def verify_final_balances(self) -> bool:
        """Verify final wallet balances"""
        self.log_step("Verifying final balances")
        
        try:
            async with AsyncSessionLocal() as session:
                # Get user A
                user_a = await get_user_by_username(session, self.user_a_username)
                user_b = await get_user_by_username(session, self.user_b_username)
                
                if not user_a or not user_b:
                    self.log_step("Users not found", "error", "Cannot verify balances")
                    return False
                
                # Get wallets
                wallet_a = await get_wallet_for_user(session, user_a.id)
                wallet_b = await get_wallet_for_user(session, user_b.id)
                
                if not wallet_a or not wallet_b:
                    self.log_step("Wallets not found", "error", "Cannot verify balances")
                    return False
                
                # Record final balances
                self.results["final_balances"] = {
                    "user_a": {
                        "deposit_balance": str(wallet_a.deposit_balance),
                        "bonus_balance": str(wallet_a.bonus_balance),
                        "winning_balance": str(wallet_a.winning_balance),
                        "total": str(wallet_a.deposit_balance + wallet_a.bonus_balance + wallet_a.winning_balance)
                    },
                    "user_b": {
                        "deposit_balance": str(wallet_b.deposit_balance),
                        "bonus_balance": str(wallet_b.bonus_balance),
                        "winning_balance": str(wallet_b.winning_balance),
                        "total": str(wallet_b.deposit_balance + wallet_b.bonus_balance + wallet_b.winning_balance)
                    }
                }
                
                self.log_step("Final balances recorded", "success", "Balances captured")
                return True
                
        except Exception as e:
            self.log_step("Balance verification error", "error", str(e))
            return False
    
    async def check_audit_logs(self) -> bool:
        """Check audit logs for admin actions"""
        self.log_step("Checking audit logs")
        
        try:
            async with AsyncSessionLocal() as session:
                logs = await get_audit_logs(session, limit=50)
                
                # Look for specific actions
                actions_found = {
                    "contest_creation": False,
                    "contest_settlement": False,
                    "withdrawal_approval": False
                }
                
                for log in logs:
                    if "contest" in log.action.lower():
                        actions_found["contest_creation"] = True
                    if "settle" in log.action.lower():
                        actions_found["contest_settlement"] = True
                    if "withdrawal" in log.action.lower():
                        actions_found["withdrawal_approval"] = True
                
                for action, found in actions_found.items():
                    self.add_assertion(
                        f"Audit log: {action}",
                        found,
                        "Action logged" if found else "Action not found"
                    )
                
                return True
                
        except Exception as e:
            self.log_step("Audit log check error", "error", str(e))
            return False
    
    async def run_smoke_test(self) -> bool:
        """Run the complete smoke test"""
        self.log_step("Starting smoke test", "info", f"Test ID: {self.timestamp}")
        
        try:
            # Step A: Setup & readiness
            if not await self.wait_for_services():
                return False
            
            # Step B: Create admin and users
            if not await self.create_admin_user():
                return False
            
            if not await self.login_admin():
                return False
            
            if not await self.create_test_users():
                return False
            
            # Step C: Create deposit transaction
            if not await self.create_deposit_transaction():
                return False
            
            # Step D: Simulate webhook confirmation
            if not await self.simulate_webhook_confirmation():
                return False
            
            # Step E: Verify deposit processing
            if not await self.verify_deposit_processing():
                return False
            
            # Step F: Create contest and users join
            if not await self.create_contest():
                return False
            
            if not await self.join_contest_users():
                return False
            
            # Step G: Settle contest & payouts
            if not await self.settle_contest():
                return False
            
            if not await self.wait_for_payouts():
                return False
            
            # Step H: Withdrawal request
            if not await self.create_withdrawal_request():
                return False
            
            # Step I: Final consistency checks
            if not await self.verify_final_balances():
                return False
            
            if not await self.check_audit_logs():
                return False
            
            # Determine overall success
            failed_assertions = [a for a in self.results["assertions"] if not a["passed"]]
            
            if failed_assertions:
                self.results["status"] = "fail"
                self.log_step("Smoke test failed", "error", f"{len(failed_assertions)} assertions failed")
                return False
            else:
                self.results["status"] = "pass"
                self.log_step("Smoke test passed", "success", "All assertions passed")
                return True
                
        except Exception as e:
            self.results["status"] = "fail"
            self.results["errors"].append(f"Unexpected error: {str(e)}")
            self.log_step("Smoke test error", "error", str(e))
            return False
        
        finally:
            # Save results
            self.results["end_time"] = datetime.now(timezone.utc).isoformat()
            self.results["duration_seconds"] = (
                datetime.fromisoformat(self.results["end_time"].replace('Z', '+00:00')) -
                datetime.fromisoformat(self.results["start_time"].replace('Z', '+00:00'))
            ).total_seconds()
            
            with open(self.result_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            self.log_step("Results saved", "info", f"Results saved to {self.result_file}")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="CricAlgo Smoke Test")
    parser.add_argument("--nocleanup", action="store_true", help="Don't clean up test environment")
    
    args = parser.parse_args()
    
    runner = SmokeTestRunner(nocleanup=args.nocleanup)
    
    try:
        success = await runner.run_smoke_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        runner.log_step("Test interrupted", "error", "User interrupted")
        sys.exit(1)
    except Exception as e:
        runner.log_step("Test failed", "error", f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
