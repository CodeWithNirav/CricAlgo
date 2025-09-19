"""
CricAlgo FastAPI Application
Main entry point for the application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router
from app.api.v1.auth import router as auth_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.contest import router as contest_router
from app.api.v1.admin import router as admin_router
from app.api.v1.admin_contest import router as admin_contest_router
from app.middleware.rate_limit import RateLimitMiddleware

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

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(webhooks_router, prefix="/api/v1", tags=["webhooks"])

# Include v1 API routers
app.include_router(auth_router, prefix="/api/v1", tags=["authentication"])
app.include_router(wallet_router, prefix="/api/v1", tags=["wallet"])
app.include_router(contest_router, prefix="/api/v1", tags=["contest"])
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(admin_contest_router, prefix="/api/v1/admin", tags=["admin-contest"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
