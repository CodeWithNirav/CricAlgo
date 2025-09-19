#!/usr/bin/env python3
"""
Admin user creation script for CricAlgo

This script creates a seed admin user for the application.
It reads credentials from environment variables and generates secure passwords.

Environment Variables Required:
- SEED_ADMIN_USERNAME: Admin username
- SEED_ADMIN_EMAIL: Admin email address
- SEED_ADMIN_PASSWORD: Admin password (optional - will generate if not provided)

Usage:
    python scripts/create_admin.py

The script will:
1. Create an admin user with hashed password
2. Generate TOTP secret for 2FA
3. Print QR code URL for authenticator app setup
"""

import asyncio
import os
import secrets
import string
import sys
from decimal import Decimal
from typing import Optional

# Ensure UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

import pyotp
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.admin import Admin
from app.repos.user_repo import create_user
from app.repos.wallet_repo import create_wallet_for_user
from app.models.enums import UserStatus


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_secure_password(length: int = 16) -> str:
    """Generate a secure random password."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def generate_totp_secret() -> str:
    """Generate a TOTP secret for 2FA."""
    return pyotp.random_base32()


def generate_totp_url(username: str, secret: str) -> str:
    """Generate TOTP URL for authenticator app setup."""
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="CricAlgo"
    )


async def create_admin_user(
    session: AsyncSession,
    username: str,
    email: str,
    password: str
) -> Admin:
    """Create an admin user in the database."""
    
    # Generate TOTP secret
    totp_secret = generate_totp_secret()
    
    # Hash password
    password_hash = hash_password(password)
    
    # Create admin user
    admin = Admin(
        username=username,
        email=email,
        password_hash=password_hash,
        totp_secret=totp_secret
    )
    
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    
    return admin


async def main():
    """Main function to create admin user."""
    
    # Read environment variables
    username = os.getenv('SEED_ADMIN_USERNAME')
    email = os.getenv('SEED_ADMIN_EMAIL')
    password = os.getenv('SEED_ADMIN_PASSWORD')
    
    # Validate required environment variables
    if not username:
        print("ERROR: SEED_ADMIN_USERNAME environment variable is required")
        print("   Set it with: export SEED_ADMIN_USERNAME='admin'")
        return
    
    if not email:
        print("ERROR: SEED_ADMIN_EMAIL environment variable is required")
        print("   Set it with: export SEED_ADMIN_EMAIL='admin@cricalgo.com'")
        return
    
    # Generate password if not provided
    if not password:
        password = generate_secure_password()
        print(f"Generated secure password: {password}")
        print("IMPORTANT: Save this password and change it after first login!")
        print()
    
    print(f"Creating admin user: {username}")
    print(f"Email: {email}")
    print()
    
    try:
        # Create admin user
        async with AsyncSessionLocal() as session:
            # Check if admin already exists
            from app.repos.admin_repo import get_admin_by_username
            existing_admin = await get_admin_by_username(session, username)
            if existing_admin:
                print("SUCCESS: Admin user already exists!")
                print(f"   Admin ID: {existing_admin.id}")
                print(f"   Username: {existing_admin.username}")
                print(f"   Email: {existing_admin.email}")
                print()
                admin = existing_admin
            else:
                admin = await create_admin_user(session, username, email, password)
                print("SUCCESS: Admin user created successfully!")
                print(f"   Admin ID: {admin.id}")
                print(f"   Username: {admin.username}")
                print(f"   Email: {admin.email}")
                print()
            
            # Generate TOTP URL
            totp_url = generate_totp_url(username, admin.totp_secret)
            print("2FA Setup:")
            print(f"   TOTP Secret: {admin.totp_secret}")
            print(f"   QR Code URL: {totp_url}")
            print()
            print("To set up 2FA:")
            print("   1. Install an authenticator app (Google Authenticator, Authy, etc.)")
            print("   2. Scan the QR code or enter the secret manually")
            print("   3. Use the generated codes to log in")
            print()
            
            # Create a regular user account for the admin (for wallet functionality)
            try:
                user = await create_user(
                    session=session,
                    telegram_id=0,  # Special admin telegram ID
                    username=f"admin_{username}",
                    status=UserStatus.ACTIVE.value
                )
                
                # Create wallet for the admin user
                await create_wallet_for_user(session, user.id)
                
                print("SUCCESS: Admin user account and wallet created!")
                print(f"   User ID: {user.id}")
                print(f"   Telegram ID: {user.telegram_id}")
                
            except Exception as e:
                print(f"WARNING: Could not create user account for admin: {e}")
            
            print()
            print("Setup complete! You can now log in with:")
            print(f"   Username: {username}")
            print(f"   Password: {password}")
            
    except Exception as e:
        print(f"ERROR creating admin user: {e}")
        return


if __name__ == "__main__":
    print("CricAlgo Admin User Creation Script")
    print("=" * 50)
    print()
    
    # Check if we're in the right directory
    if not os.path.exists("app"):
        print("ERROR: Please run this script from the project root directory")
        print("   Current directory should contain the 'app' folder")
        exit(1)
    
    # Run the async main function
    asyncio.run(main())
