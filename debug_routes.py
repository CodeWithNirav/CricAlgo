from app.main import app

print("=== ALL ADMIN ROUTES ===")
for route in app.routes:
    if hasattr(route, 'path') and '/admin' in route.path:
        methods = getattr(route, 'methods', 'N/A')
        print(f"{methods} {route.path}")

print("\n=== ALL ROUTES WITH 'matches' ===")
for route in app.routes:
    if hasattr(route, 'path') and 'matches' in route.path:
        methods = getattr(route, 'methods', 'N/A')
        print(f"{methods} {route.path}")

print("\n=== ALL ROUTES WITH 'deposits' ===")
for route in app.routes:
    if hasattr(route, 'path') and 'deposits' in route.path:
        methods = getattr(route, 'methods', 'N/A')
        print(f"{methods} {route.path}")
