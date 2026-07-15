# ---- Base image ----
# Slim image keeps the final image small, which speeds up
# push/pull to ECR and cold starts on ECS/EC2.
FROM python:3.12-slim AS base

WORKDIR /code

# System deps needed to build some scientific-python wheels.
# (Kept minimal; scikit-learn/numpy ship manylinux wheels so this
# is usually a no-op, but it protects against slow source builds.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Dependencies layer ----
# Copying requirements first lets Docker cache this layer so that
# code-only changes don't reinstall the whole dependency tree.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- App layer ----
COPY app ./app
COPY model ./model

# Model is trained ahead of time and shipped inside the image so the
# container has zero cold-start training cost — it just loads a file.
# (If you'd rather train at build time, add:
#   COPY train_model.py .
#   RUN python train_model.py
# before this line, and drop model/ from the build context.)

EXPOSE 8000

# A few workers gives you real concurrency for a CPU-bound sklearn model
# without needing a separate process manager. Tune --workers to vCPU count.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
