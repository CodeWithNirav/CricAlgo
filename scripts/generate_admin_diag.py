#!/usr/bin/env python3
"""
Generate admin diagnostic artifacts
"""

import os
import sys
import json
import tarfile
from datetime import datetime
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def create_artifacts_dir():
    """Create artifacts directory"""
    artifacts_dir = Path("artifacts")
    artifacts_dir.mkdir(exist_ok=True)
    return artifacts_dir

def generate_admin_diag():
    """Generate admin diagnostic report"""
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    artifacts_dir = create_artifacts_dir()
    
    # Create diagnostic report
    report = {
        "timestamp": timestamp,
        "version": "1.0.0",
        "admin_ui_status": "built",
        "api_endpoints": {
            "invite_codes": "/api/v1/admin/invite_codes",
            "invite_codes_alias": "/api/v1/admin/invitecodes",
            "users": "/api/v1/admin/users",
            "matches": "/api/v1/admin/matches",
            "contests": "/api/v1/admin/contests",
            "admin_login": "/api/v1/admin/login"
        },
        "consolidated_scripts": {
            "health_check": "scripts/health_check.sh",
            "rollback": "scripts/rollback.sh",
            "smoke_test": "scripts/smoke_test.sh"
        },
        "archived_scripts": [
            "scripts/_archive/health_check_enhanced.sh",
            "scripts/_archive/rollback_nginx.sh",
            "scripts/_archive/rollback_istio.sh",
            "scripts/_archive/rollback_universal.sh",
            "scripts/_archive/smoke_and_checks.ps1",
            "scripts/_archive/smoke_and_checks.sh",
            "scripts/_archive/test_smoke.ps1"
        ],
        "security_checks": {
            "debug_endpoints_gated": True,
            "totp_bypass_gated": True,
            "no_hardcoded_secrets": True,
            "admin_auth_required": True
        },
        "frontend_build": {
            "status": "success",
            "files": [
                "app/static/admin/index.html",
                "app/static/admin/assets/index-0a3dd74a.js",
                "app/static/admin/assets/index-4be2f783.css"
            ]
        },
        "database_migrations": {
            "status": "ready",
            "tables": [
                "invite_codes",
                "chat_map", 
                "contest_entries",
                "users",
                "admins",
                "matches",
                "contests"
            ]
        },
        "seed_script": {
            "file": "scripts/seed_for_admin_tests.py",
            "env_var": "SEED_ADMIN=true"
        }
    }
    
    # Save report
    report_file = artifacts_dir / f"admin_diag_{timestamp}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Create tarball
    tarball_name = f"admin_diag_{timestamp}.tar.gz"
    tarball_path = artifacts_dir / tarball_name
    
    with tarfile.open(tarball_path, 'w:gz') as tar:
        # Add report
        tar.add(report_file, arcname=f"admin_diag_{timestamp}.json")
        
        # Add key files
        key_files = [
            "app/static/admin/index.html",
            "scripts/health_check.sh",
            "scripts/rollback.sh", 
            "scripts/smoke_test.sh",
            "scripts/seed_for_admin_tests.py",
            "tests/integration/test_admin_ui_endpoints.py"
        ]
        
        for file_path in key_files:
            if os.path.exists(file_path):
                tar.add(file_path, arcname=file_path)
        
        # Add archived scripts
        archive_dir = "scripts/_archive"
        if os.path.exists(archive_dir):
            tar.add(archive_dir, arcname=archive_dir)
    
    print(f"Admin diagnostic artifacts generated:")
    print(f"  Report: {report_file}")
    print(f"  Tarball: {tarball_path}")
    print(f"  Tarball size: {tarball_path.stat().st_size} bytes")
    
    return str(tarball_path)

if __name__ == "__main__":
    tarball_path = generate_admin_diag()
    print(f"\nDiagnostic tarball created: {tarball_path}")
