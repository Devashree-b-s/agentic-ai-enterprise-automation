"""Basic tests for root and health endpoints."""

from fastapi.testclient import TestClient


def test_read_root(client: TestClient):
    """Verify that the GET / endpoint returns 200 and expected metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["version"] == "0.1.0"
    assert "Welcome" in data["message"]


def test_health_check(client: TestClient):
    """Verify that the GET /health endpoint returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "enterprise-backend"
