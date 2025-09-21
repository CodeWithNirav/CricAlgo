#!/usr/bin/env python3
"""
Test server startup
"""
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.main import app
    print("✅ App imported successfully")
    print(f"✅ App type: {type(app)}")
    
    # Check routes
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    print(f"✅ Found {len(routes)} routes")
    
    # Look for admin routes
    admin_routes = [r for r in routes if 'admin' in r]
    print(f"✅ Admin routes: {admin_routes}")
    
    # Look for matches routes
    matches_routes = [r for r in routes if 'matches' in r]
    print(f"✅ Matches routes: {matches_routes}")
    
except Exception as e:
    print(f"❌ Error importing app: {e}")
    import traceback
    traceback.print_exc()
