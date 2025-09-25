#!/usr/bin/env python3
"""
Create an admin JWT token for testing purposes
"""

import os
import sys
from datetime import datetime, timedelta
from jose import jwt

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings

def create_admin_token(admin_id: str, username: str = "admin"):
    """Create an admin JWT token"""
    to_encode = {
        "sub": admin_id,
        "username": username,
        "type": "admin",
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    token = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token

if __name__ == "__main__":
    # Get admin ID from command line or use default
    admin_id = sys.argv[1] if len(sys.argv) > 1 else "a536c019-ae63-496d-b8e9-dee6feecf7c5"
    
    token = create_admin_token(admin_id)
    print(f"Admin Token: {token}")
    print(f"Admin ID: {admin_id}")
    print(f"Username: admin")
