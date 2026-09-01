from fastapi.testclient import TestClient
from basketlab.api import app


def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rules_endpoint():
    response = TestClient(app).get("/api/rules?limit=5&min_lift=1")
    assert response.status_code == 200
    assert len(response.json()) <= 5


def test_experiment_endpoint_runs_and_returns_summary():
    response = TestClient(app).post("/api/experiments", json={"budget": 2})
    assert response.status_code == 200
    assert "best_config" in response.json()
