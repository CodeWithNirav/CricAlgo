"""
Webhook testing fixtures and utilities
"""

import json
import asyncio
from typing import Dict, Any, Optional
from httpx import AsyncClient


class WebhookTestHelper:
    """Helper class for webhook testing operations."""
    
    def __init__(self, client: AsyncClient, base_url: str = "http://test"):
        self.client = client
        self.base_url = base_url
    
    async def send_deposit_webhook(
        self,
        tx_hash: str,
        confirmations: int = 12,
        amount: str = "100.00",
        currency: str = "USDT",
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a deposit confirmation webhook."""
        payload = {
            "tx_hash": tx_hash,
            "confirmations": confirmations,
            "amount": amount,
            "currency": currency,
            "status": "confirmed",
            "block_number": 12345678,
            **kwargs
        }
        
        if user_id:
            payload["user_id"] = user_id
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/webhooks/bep20",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }
    
    async def send_withdrawal_webhook(
        self,
        tx_hash: str,
        confirmations: int = 12,
        amount: str = "50.00",
        currency: str = "USDT",
        user_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Send a withdrawal confirmation webhook."""
        payload = {
            "tx_hash": tx_hash,
            "confirmations": confirmations,
            "amount": amount,
            "currency": currency,
            "status": "confirmed",
            "block_number": 12345679,
            **kwargs
        }
        
        if user_id:
            payload["user_id"] = user_id
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/webhooks/bep20",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }
    
    async def send_pending_webhook(
        self,
        tx_hash: str,
        confirmations: int = 1,
        amount: str = "100.00",
        currency: str = "USDT",
        **kwargs
    ) -> Dict[str, Any]:
        """Send a pending transaction webhook."""
        payload = {
            "tx_hash": tx_hash,
            "confirmations": confirmations,
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "block_number": 12345677,
            **kwargs
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/webhooks/bep20",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }
    
    async def send_failed_webhook(
        self,
        tx_hash: str,
        reason: str = "Insufficient gas",
        **kwargs
    ) -> Dict[str, Any]:
        """Send a failed transaction webhook."""
        payload = {
            "tx_hash": tx_hash,
            "status": "failed",
            "reason": reason,
            "block_number": 12345680,
            **kwargs
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/v1/webhooks/bep20",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        return {
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        }


def create_webhook_payload(
    tx_hash: str,
    confirmations: int = 12,
    amount: str = "100.00",
    currency: str = "USDT",
    status: str = "confirmed",
    **kwargs
) -> Dict[str, Any]:
    """Create a webhook payload with common defaults."""
    return {
        "tx_hash": tx_hash,
        "confirmations": confirmations,
        "amount": amount,
        "currency": currency,
        "status": status,
        "block_number": 12345678,
        "timestamp": 1640995200,  # 2022-01-01 00:00:00 UTC
        **kwargs
    }


def create_deposit_webhook_payload(
    tx_hash: str,
    amount: str = "100.00",
    currency: str = "USDT",
    confirmations: int = 12,
    **kwargs
) -> Dict[str, Any]:
    """Create a deposit webhook payload."""
    return create_webhook_payload(
        tx_hash=tx_hash,
        amount=amount,
        currency=currency,
        confirmations=confirmations,
        status="confirmed",
        **kwargs
    )


def create_withdrawal_webhook_payload(
    tx_hash: str,
    amount: str = "50.00",
    currency: str = "USDT",
    confirmations: int = 12,
    **kwargs
) -> Dict[str, Any]:
    """Create a withdrawal webhook payload."""
    return create_webhook_payload(
        tx_hash=tx_hash,
        amount=amount,
        currency=currency,
        confirmations=confirmations,
        status="confirmed",
        **kwargs
    )


async def simulate_webhook_retry(
    webhook_helper: WebhookTestHelper,
    payload: Dict[str, Any],
    max_retries: int = 3,
    delay: float = 0.1
) -> list:
    """
    Simulate webhook retry behavior.
    
    Args:
        webhook_helper: WebhookTestHelper instance
        payload: Webhook payload to send
        max_retries: Maximum number of retries
        delay: Delay between retries
    
    Returns:
        List of responses from all attempts
    """
    responses = []
    
    for attempt in range(max_retries):
        response = await webhook_helper.client.post(
            f"{webhook_helper.base_url}/api/v1/webhooks/bep20",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        responses.append({
            "attempt": attempt + 1,
            "status_code": response.status_code,
            "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
        })
        
        if response.status_code < 400:
            break
        
        if attempt < max_retries - 1:
            await asyncio.sleep(delay)
    
    return responses
