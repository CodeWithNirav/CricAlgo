#!/usr/bin/env python3
"""
Basic test script to verify smoke test functionality
"""

import sys
import os

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    try:
        # Add the project root to the Python path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import scripts.smoke_test
        print("✓ scripts.smoke_test imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import scripts.smoke_test: {e}")
        return False
    
    try:
        from scripts.smoke_test import SmokeTestRunner
        print("✓ SmokeTestRunner imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import SmokeTestRunner: {e}")
        return False
    
    return True

def test_runner_creation():
    """Test if SmokeTestRunner can be created"""
    print("Testing runner creation...")
    
    try:
        # Add the project root to the Python path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from scripts.smoke_test import SmokeTestRunner
        runner = SmokeTestRunner()
        print("✓ SmokeTestRunner created successfully")
        print(f"  - Test ID: {runner.timestamp}")
        print(f"  - User A: {runner.user_a_username}")
        print(f"  - User B: {runner.user_b_username}")
        print(f"  - Match ID: {runner.match_id}")
        print(f"  - TX Hash: {runner.tx_hash}")
        return True
    except Exception as e:
        print(f"✗ Failed to create SmokeTestRunner: {e}")
        return False

def test_help():
    """Test help functionality"""
    print("Testing help functionality...")
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, "scripts/smoke_test.py", "--help"
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and "usage:" in result.stdout:
            print("✓ Help functionality works")
            return True
        else:
            print(f"✗ Help functionality failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Help test failed: {e}")
        return False

def test_artifacts_dir():
    """Test if artifacts directory exists"""
    print("Testing artifacts directory...")
    
    if os.path.exists("artifacts"):
        print("✓ Artifacts directory exists")
        return True
    else:
        print("✗ Artifacts directory not found")
        return False

def main():
    """Run all tests"""
    print("CricAlgo Smoke Test - Basic Validation")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_runner_creation,
        test_help,
        test_artifacts_dir
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All basic tests passed!")
        print("\nTo run the full smoke test:")
        print("1. Start services: docker-compose -f docker-compose.test.yml up -d --build")
        print("2. Wait 30 seconds for services to be ready")
        print("3. Run test: python scripts/smoke_test.py")
        print("4. Check results: artifacts/smoke_test_result.json")
        print("5. Clean up: docker-compose -f docker-compose.test.yml down -v")
        return True
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
