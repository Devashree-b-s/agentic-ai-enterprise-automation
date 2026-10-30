"""Basic tests for root and health endpoints."""

import sys
from pathlib import Path

# Ensure 'backend' directory is in sys.path so 'app' can be imported cleanly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from app.main import app

# Create test client for simulating HTTP requests
client = TestClient(app)


def test_read_root():
    """Verify that the GET / endpoint returns 200 and expected metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["version"] == "0.1.0"
    assert "Welcome" in data["message"]


def test_health_check():
    """Verify that the GET /health endpoint returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "enterprise-backend"
