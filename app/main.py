"""
CricAlgo FastAPI Application
Main entry point for the application
"""

from fastapi import FastAPI
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router

# Create FastAPI app instance
app = FastAPI(
    title="CricAlgo API",
    description="Cricket Algorithm Trading Bot API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(webhooks_router, prefix="/api/v1", tags=["webhooks"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
