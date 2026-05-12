# ---- RAG Service (Pinecone) Dockerfile ----
# Base: slim Python 3.11 image
# llama-cpp-python is compiled from source for CPU-only inference.
# For GPU support, replace base image with nvidia/cuda and set CMAKE_ARGS.

FROM python:3.11-slim

# System dependencies needed to compile llama-cpp-python
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
# llama-cpp-python requires CMAKE_ARGS for CPU-only build
ENV CMAKE_ARGS="-DLLAMA_BLAS=OFF -DLLAMA_CUBLAS=OFF"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY main.py rag_pipeline.py seed_pinecone.py inspect_pinecone.py listings_seed_data.py ./

# The GGUF model file is NOT baked into the image.
# Mount it at runtime via Docker volumes (see docker-compose.yml).
RUN mkdir -p ./models

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
