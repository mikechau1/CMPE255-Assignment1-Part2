from fastapi.testclient import TestClient
from basketlab.api import app


def test_vite_origin_is_allowed_for_browser_fetches():
    response = TestClient(app).options(
        "/api/summary",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"

