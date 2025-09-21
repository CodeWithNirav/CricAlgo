#!/usr/bin/env python3
"""
Test router registration
"""
from app.main import app

print("🔍 Checking registered routes...")
print("=" * 50)

for route in app.routes:
    if hasattr(route, 'path'):
        print(f"Route: {route.path}")
        if hasattr(route, 'methods'):
            print(f"  Methods: {route.methods}")
        if hasattr(route, 'name'):
            print(f"  Name: {route.name}")
        print()

print("🔍 Looking for admin matches routes...")
admin_routes = [route for route in app.routes if hasattr(route, 'path') and 'admin' in route.path and 'matches' in route.path]
print(f"Found {len(admin_routes)} admin matches routes:")
for route in admin_routes:
    print(f"  {route.path}")
