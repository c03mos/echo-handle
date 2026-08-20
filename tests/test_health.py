from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_extract_audio_validation_error() -> None:
    response = client.post("/api/v1/media/extract-audio", json={})
    assert response.status_code == 422
