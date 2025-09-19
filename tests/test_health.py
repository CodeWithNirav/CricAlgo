"""
Test health endpoint
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test that health endpoint returns 200 and correct response"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_endpoint_direct():
    """Test health endpoint directly"""
    from app.api.health import health_check
    import asyncio
    
    result = asyncio.run(health_check())
    assert result == {"status": "ok"}
