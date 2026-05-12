# ---- Image Analyser Service Dockerfile (CPU-only) ----
# PyTorch CPU wheel is fetched from the official PyTorch index.
# For GPU support: switch to nvidia/cuda base + remove +cpu suffix from torch.

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        # Pillow dependencies
        libjpeg-dev \
        libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py model.py dataset.py train.py ./

# Checkpoint is mounted at runtime — not baked into the image.
RUN mkdir -p ./checkpoints ./data

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
