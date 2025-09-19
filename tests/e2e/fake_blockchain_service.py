"""
Fake blockchain service for E2E testing

This service simulates a blockchain webhook service that sends transaction
confirmations to the main application. It stores webhook data in-memory
and can be used to test webhook handling and idempotency.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for webhook data
webhook_data: Dict[str, Dict[str, Any]] = {}
processed_webhooks: Dict[str, int] = {}  # Track how many times each webhook was processed


class WebhookPayload(BaseModel):
    """Webhook payload model"""
    tx_hash: str
    confirmations: int
    amount: Optional[str] = None
    currency: Optional[str] = "USDT"
    status: Optional[str] = "confirmed"
    block_number: Optional[int] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class WebhookResponse(BaseModel):
    """Webhook response model"""
    success: bool
    message: str
    tx_hash: str
    processed_at: str


# Create FastAPI app
app = FastAPI(
    title="Fake Blockchain Service",
    description="Simulates blockchain webhook service for testing",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "fake-blockchain",
        "status": "running",
        "webhooks_received": len(webhook_data),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/webhooks")
async def list_webhooks():
    """List all received webhooks"""
    return {
        "webhooks": webhook_data,
        "processed_counts": processed_webhooks,
        "total_webhooks": len(webhook_data)
    }


@app.get("/webhooks/{tx_hash}")
async def get_webhook(tx_hash: str):
    """Get webhook data for a specific transaction"""
    if tx_hash not in webhook_data:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    return {
        "tx_hash": tx_hash,
        "data": webhook_data[tx_hash],
        "processed_count": processed_webhooks.get(tx_hash, 0)
    }


@app.post("/webhook", response_model=WebhookResponse)
async def receive_webhook(payload: WebhookPayload):
    """
    Receive a webhook from the blockchain simulation.
    
    This endpoint simulates receiving webhook data from a blockchain service
    and stores it in memory for testing purposes.
    """
    tx_hash = payload.tx_hash
    
    # Store webhook data
    webhook_data[tx_hash] = {
        "tx_hash": tx_hash,
        "confirmations": payload.confirmations,
        "amount": payload.amount,
        "currency": payload.currency,
        "status": payload.status,
        "block_number": payload.block_number,
        "user_id": payload.user_id,
        "metadata": payload.metadata or {},
        "received_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Track processing count
    processed_webhooks[tx_hash] = processed_webhooks.get(tx_hash, 0) + 1
    
    logger.info(f"Received webhook for tx_hash: {tx_hash}, confirmations: {payload.confirmations}")
    
    return WebhookResponse(
        success=True,
        message="Webhook received successfully",
        tx_hash=tx_hash,
        processed_at=datetime.now(timezone.utc).isoformat()
    )


@app.post("/webhook/simulate-confirmation")
async def simulate_confirmation(payload: WebhookPayload):
    """
    Simulate a transaction confirmation by sending webhook to main app.
    
    This endpoint simulates the blockchain service sending a confirmation
    webhook to the main application.
    """
    # This would normally send HTTP request to main app
    # For testing, we'll just store the data and return success
    tx_hash = payload.tx_hash
    
    # Store as confirmed webhook
    webhook_data[tx_hash] = {
        "tx_hash": tx_hash,
        "confirmations": payload.confirmations,
        "amount": payload.amount,
        "currency": payload.currency,
        "status": "confirmed",
        "block_number": payload.block_number,
        "user_id": payload.user_id,
        "metadata": payload.metadata or {},
        "received_at": datetime.now(timezone.utc).isoformat(),
        "simulated": True
    }
    
    processed_webhooks[tx_hash] = processed_webhooks.get(tx_hash, 0) + 1
    
    logger.info(f"Simulated confirmation for tx_hash: {tx_hash}")
    
    return WebhookResponse(
        success=True,
        message="Confirmation simulated successfully",
        tx_hash=tx_hash,
        processed_at=datetime.now(timezone.utc).isoformat()
    )


@app.delete("/webhooks/{tx_hash}")
async def delete_webhook(tx_hash: str):
    """Delete webhook data for a specific transaction"""
    if tx_hash not in webhook_data:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    del webhook_data[tx_hash]
    if tx_hash in processed_webhooks:
        del processed_webhooks[tx_hash]
    
    return {"message": f"Webhook {tx_hash} deleted successfully"}


@app.delete("/webhooks")
async def clear_all_webhooks():
    """Clear all webhook data"""
    webhook_data.clear()
    processed_webhooks.clear()
    
    return {"message": "All webhooks cleared successfully"}


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    return {
        "total_webhooks": len(webhook_data),
        "unique_transactions": len(set(webhook_data.keys())),
        "total_processing_attempts": sum(processed_webhooks.values()),
        "average_processing_per_tx": (
            sum(processed_webhooks.values()) / len(processed_webhooks)
            if processed_webhooks else 0
        ),
        "service_uptime": "unknown"  # Could implement proper uptime tracking
    }


if __name__ == "__main__":
    # Run the fake blockchain service
    uvicorn.run(
        "fake_blockchain_service:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
        log_level="info"
    )
