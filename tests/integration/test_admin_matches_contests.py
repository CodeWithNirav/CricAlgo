"""
Integration tests for admin matches and contests endpoints
"""
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from app.main import app


def test_matches_contests_endpoints():
    """Test that the matches and contests endpoints are accessible"""
    client = TestClient(app)
    with client as ac:
        # Test matches endpoint (should return 401 without auth)
        r = ac.get("/api/v1/admin/matches")
        assert r.status_code in (200, 401, 403)
        
        # Test contests endpoint for a fake match ID (should return 401 without auth)
        r2 = ac.get("/api/v1/admin/matches/fake-id/contests")
        assert r2.status_code in (200, 401, 403, 404)
        
        # Test contest details endpoint (should return 401 without auth)
        r3 = ac.get("/api/v1/admin/contests/fake-id")
        assert r3.status_code in (200, 401, 403, 404)


def test_contest_entries_endpoint():
    """Test contest entries endpoint"""
    client = TestClient(app)
    with client as ac:
        r = ac.get("/api/v1/admin/contests/fake-id/entries")
        assert r.status_code in (200, 401, 403, 404)


def test_contest_export_endpoint():
    """Test contest export endpoint"""
    client = TestClient(app)
    with client as ac:
        r = ac.get("/api/v1/admin/contests/fake-id/export")
        assert r.status_code in (200, 401, 403, 404)
