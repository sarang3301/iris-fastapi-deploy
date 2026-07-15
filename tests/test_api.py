import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    # A context manager ensures FastAPI's lifespan (startup/shutdown)
    # events run, so the model is actually loaded before requests hit it.
    with TestClient(app) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_predict(client):
    payload = {
        "sepal_length": 5.1,
        "sepal_width": 3.5,
        "petal_length": 1.4,
        "petal_width": 0.2,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "predicted_class" in body
    assert "probabilities" in body
    assert body["predicted_class"] in ("setosa", "versicolor", "virginica")


def test_predict_batch(client):
    payload = [
        {
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2,
        },
        {
            "sepal_length": 6.7,
            "sepal_width": 3.0,
            "petal_length": 5.2,
            "petal_width": 2.3,
        },
    ]
    response = client.post("/predict/batch", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
