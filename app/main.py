"""
app/main.py

FastAPI application that serves predictions from a pre-trained
scikit-learn Iris classifier.

Latency-optimization choices made here (see README for details):
  - Model is loaded ONCE at startup (lifespan event), not per request.
  - Single-row and batch prediction endpoints both reuse the same
    in-memory model object (no disk I/O per request).
  - numpy arrays are built directly instead of going through pandas.
  - A lightweight timing middleware reports per-request latency so
    regressions are visible without extra tooling.
"""

import time
from contextlib import asynccontextmanager
import os

import boto3
import joblib
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.schemas import IrisFeatures, PredictionResponse, HealthResponse

MODEL_PATH = "model/iris_model.joblib"
S3_BUCKET = os.environ.get("MODEL_S3_BUCKET", "sarang-iris-model-artifacts-865122443628")
S3_KEY = os.environ.get("MODEL_S3_KEY", "models/latest/iris_model.joblib")
LOCAL_MODEL_PATH = "/tmp/iris_model.joblib"
USE_S3 = os.environ.get("USE_S3_MODEL", "false").lower() == "true"

ml_state: dict = {"model": None, "target_names": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load model once, keep it in memory for the life of the process
    if USE_S3:
        s3 = boto3.client("s3")
        s3.download_file(S3_BUCKET, S3_KEY, LOCAL_MODEL_PATH)
        bundle = joblib.load(LOCAL_MODEL_PATH)
        print(f"Model loaded from s3://{S3_BUCKET}/{S3_KEY}", flush=True)
    else:
        bundle = joblib.load(MODEL_PATH)
        print(f"Model loaded from local path {MODEL_PATH}", flush=True)

    ml_state["model"] = bundle["model"]
    ml_state["target_names"] = bundle["target_names"]
    yield
    # Shutdown: nothing to clean up for this simple model
    ml_state.clear()


app = FastAPI(
    title="Iris Classifier API",
    description="A minimal end-to-end example: sklearn model served with FastAPI, "
    "containerized with Docker, deployable to AWS.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time-ms"] = f"{duration_ms:.2f}"
    return response


@app.get("/", tags=["meta"])
def root():
    return {"message": "Iris Classifier API. See /docs for interactive usage."}


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    return HealthResponse(
        status="ok",
        model_loaded=ml_state["model"] is not None,
    )


@app.post("/predict", response_model=PredictionResponse, tags=["inference"])
def predict(features: IrisFeatures):
    start = time.perf_counter()

    model = ml_state["model"]
    target_names = ml_state["target_names"]

    x = np.array(
        [
            [
                features.sepal_length,
                features.sepal_width,
                features.petal_length,
                features.petal_width,
            ]
        ]
    )

    pred_idx = int(model.predict(x)[0])
    proba = model.predict_proba(x)[0]

    latency_ms = (time.perf_counter() - start) * 1000

    return PredictionResponse(
        predicted_class=target_names[pred_idx],
        predicted_class_index=pred_idx,
        probabilities={
            name: float(p) for name, p in zip(target_names, proba)
        },
        latency_ms=round(latency_ms, 3),
    )


@app.post("/predict/batch", tags=["inference"])
def predict_batch(items: list[IrisFeatures]):
    """
    Batch endpoint: scores many rows in a single call to the model
    instead of one HTTP round trip per row. This is the main lever
    for throughput/latency when a client needs many predictions.
    """
    start = time.perf_counter()

    model = ml_state["model"]
    target_names = ml_state["target_names"]

    x = np.array(
        [
            [f.sepal_length, f.sepal_width, f.petal_length, f.petal_width]
            for f in items
        ]
    )

    preds = model.predict(x)
    probas = model.predict_proba(x)

    latency_ms = (time.perf_counter() - start) * 1000

    results = [
        {
            "predicted_class": target_names[int(p)],
            "predicted_class_index": int(p),
            "probabilities": {
                name: float(prob) for name, prob in zip(target_names, row)
            },
        }
        for p, row in zip(preds, probas)
    ]

    return JSONResponse(
        {
            "results": results,
            "count": len(results),
            "latency_ms": round(latency_ms, 3),
        }
    )
