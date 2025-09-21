#!/usr/bin/env python3
"""
Test script to check what routes are registered
"""
from app.main import app

print("=== REGISTERED ROUTES ===")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        print(f"{route.methods} {route.path}")
    elif hasattr(route, 'path'):
        print(f"ROUTE: {route.path}")

print("\n=== ADMIN ROUTES ===")
for route in app.routes:
    if hasattr(route, 'path') and '/admin' in route.path:
        if hasattr(route, 'methods'):
            print(f"{route.methods} {route.path}")
        else:
            print(f"ROUTE: {route.path}")
