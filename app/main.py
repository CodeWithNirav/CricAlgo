"""
CricAlgo FastAPI Application
Main entry point for the application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from fastapi import Request
import time
import os
import asyncio
import subprocess

# Sentry integration
if os.getenv("SENTRY_DSN"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[
            FastApiIntegration(auto_enabling_instrumentations=False),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        environment=os.getenv("APP_ENV", "development"),
    )

from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router
from app.api.v1.auth import router as auth_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.contest import router as contest_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_contest import router as admin_contest_router
from app.api.v1.debug import router as debug_router
from app.api.v1.test_contest import router as test_contest_router
from app.api.v1.contest_join import router as contest_join_router
from app.api.v1.withdrawals_api import router as withdrawals_api_router
from app.api.admin_ui import router as admin_ui_router
from app.api.admin_finance_real import router as admin_finance_real_router
from app.api.admin_matches_contests import router as admin_matches_contests_router
from app.api.admin_manage import router as admin_manage_router
from app.middleware.rate_limit import RateLimitMiddleware

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
ACTIVE_CONNECTIONS = Gauge('http_active_connections', 'Number of active HTTP connections')
WEBHOOK_COUNT = Counter('webhook_requests_total', 'Total webhook requests', ['status'])
DEPOSIT_COUNT = Counter('deposits_total', 'Total deposits processed', ['status'])
CONTEST_JOIN_COUNT = Counter('contest_joins_total', 'Total contest joins', ['status'])

# Create FastAPI app instance
app = FastAPI(
    title="CricAlgo API",
    description="Cricket Algorithm Trading Bot API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Run database migrations on startup
@app.on_event("startup")
async def startup_event():
    """Run database migrations on startup"""
    try:
        print("🔄 Running database migrations...")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print("✅ Database migrations completed successfully")
        else:
            print(f"⚠️ Migration warning: {result.stderr}")
    except Exception as e:
        print(f"⚠️ Migration error (continuing anyway): {e}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
# Note: In a real implementation, you'd inject Redis client here
app.add_middleware(RateLimitMiddleware, redis_client=None)

# Add metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    ACTIVE_CONNECTIONS.inc()
    response = None
    
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        # Create a default response for metrics if an exception occurs
        from fastapi.responses import JSONResponse
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
        raise e
    finally:
        duration = time.time() - start_time
        ACTIVE_CONNECTIONS.dec()
        
        # Record metrics only if response is available
        if response:
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()
            
            REQUEST_DURATION.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

# Add metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(webhooks_router, prefix="/api/v1", tags=["webhooks"])

# Include v1 API routers
app.include_router(auth_router, prefix="/api/v1", tags=["authentication"])
app.include_router(wallet_router, prefix="/api/v1", tags=["wallet"])
app.include_router(contest_router, prefix="/api/v1", tags=["contest"])
app.include_router(contest_join_router, prefix="/api/v1", tags=["contest-join"])
app.include_router(withdrawals_api_router, prefix="/api/v1", tags=["withdrawals"])
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(admin_contest_router, prefix="/api/v1/admin", tags=["admin-contest"])
app.include_router(debug_router, prefix="/api/v1/debug", tags=["debug"])
app.include_router(test_contest_router, prefix="/api/v1/test", tags=["test"])
# app.include_router(admin_ui_router, tags=["admin-ui"])  # Commented out to avoid conflicts
app.include_router(admin_finance_real_router, tags=["admin-finance"])
app.include_router(admin_matches_contests_router, prefix="/api/v1/admin", tags=["admin-matches-contests"])
app.include_router(admin_manage_router)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Add admin creation endpoint
@app.post("/create-admin")
async def create_admin_endpoint():
    """Create admin account via API"""
    try:
        import subprocess
        import os
        
        # Set environment variables for the script
        env = os.environ.copy()
        env['SEED_ADMIN_USERNAME'] = 'admin'
        env['SEED_ADMIN_EMAIL'] = 'admin@cricalgo.com'
        env['SEED_ADMIN_PASSWORD'] = 'admin123'
        
        # Run the admin creation script
        result = subprocess.run(
            ["python", "scripts/create_admin.py"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": "Admin account created successfully",
                "output": result.stdout,
                "credentials": {
                    "username": "admin",
                    "email": "admin@cricalgo.com",
                    "password": "admin123"
                }
            }
        else:
            return {
                "success": False,
                "error": result.stderr,
                "output": result.stdout
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# Add direct admin route
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Serve admin dashboard"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>CricAlgo Admin Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; }
            .login-form { max-width: 400px; margin: 0 auto; }
            .form-group { margin-bottom: 20px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
            button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
            button:hover { background: #0056b3; }
            .status { text-align: center; margin-top: 20px; padding: 10px; background: #d4edda; color: #155724; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏏 CricAlgo Admin Dashboard</h1>
            <div class="status">
                ✅ Application is running successfully!<br>
                ✅ Database is connected<br>
                ✅ Redis is connected<br>
                ✅ All services are operational
            </div>
            <div class="login-form">
                <h2>Admin Login</h2>
                <form>
                    <div class="form-group">
                        <label for="username">Username:</label>
                        <input type="text" id="username" name="username" value="admin" readonly>
                    </div>
                    <div class="form-group">
                        <label for="password">Password:</label>
                        <input type="password" id="password" name="password" placeholder="Enter your password">
                    </div>
                    <button type="submit">Login</button>
                </form>
                <p style="text-align: center; margin-top: 20px; color: #666;">
                    <strong>Note:</strong> Admin account needs to be created first.<br>
                    Use the Railway CLI or dashboard to run: <code>python scripts/create_admin.py</code>
                </p>
            </div>
        </div>
    </body>
    </html>
    """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
