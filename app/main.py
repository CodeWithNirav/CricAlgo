"""
CricAlgo FastAPI Application
Main entry point for the application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from fastapi import Request
import time
import os

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
    
    try:
        response = await call_next(request)
        return response
    finally:
        duration = time.time() - start_time
        ACTIVE_CONNECTIONS.dec()
        
        # Record metrics
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
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(admin_contest_router, prefix="/api/v1/admin", tags=["admin-contest"])
app.include_router(debug_router, prefix="/api/v1/debug", tags=["debug"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
