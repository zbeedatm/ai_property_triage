# ---- RAG Service (Pinecone) Dockerfile ----
# Base: slim Python 3.11 image
# Default insight path: Ollama API (cloud or local) — no GGUF required.
# Optional: RAG_LLM_BACKEND=llama_cpp uses llama-cpp-python (compiled CPU-only below).

FROM python:3.11-slim

# System dependencies needed to compile llama-cpp-python (legacy backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV CMAKE_ARGS="-DLLAMA_BLAS=OFF -DLLAMA_CUBLAS=OFF"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py rag_pipeline.py seed_pinecone.py inspect_pinecone.py listings_seed_data.py ./

# GGUF only required when RAG_LLM_BACKEND=llama_cpp — mount at runtime if used.
RUN mkdir -p ./models

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
