from pydantic import BaseModel, Field


class IrisFeatures(BaseModel):
    sepal_length: float = Field(..., examples=[5.1])
    sepal_width: float = Field(..., examples=[3.5])
    petal_length: float = Field(..., examples=[1.4])
    petal_width: float = Field(..., examples=[0.2])


class PredictionResponse(BaseModel):
    predicted_class: str
    predicted_class_index: int
    probabilities: dict[str, float]
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
