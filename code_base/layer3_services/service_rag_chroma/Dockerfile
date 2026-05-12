# ---- RAG Service Dockerfile ----
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
COPY main.py rag_pipeline.py seed_chroma.py listings_seed_data.py inspect_chroma.py ./

# The GGUF model file and ChromaDB are NOT baked into the image.
# Mount them at runtime via Docker volumes (see docker-compose.yml).
# Default paths match the .env.example defaults.
RUN mkdir -p ./models ./chroma_db

EXPOSE 8000

# Run seed then start the server
# In production you would seed once separately; here it's convenient for local dev.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
