# ---- LangGraph Agent Service Dockerfile ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV CMAKE_ARGS="-DLLAMA_BLAS=OFF -DLLAMA_CUBLAS=OFF"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py agent.py tools.py benchmark.py ./
COPY .env* ./

RUN mkdir -p ./models

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
