# ---- WebUI Dockerfile ----
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir --force-reinstall "jinja2==3.1.4" "starlette==0.37.2"

COPY app.py chat_client.py webhook_client.py ./
COPY .env* ./

RUN mkdir -p ./uploads

ENV GRADIO_SERVER_NAME="0.0.0.0"

EXPOSE 7860

CMD ["python", "app.py"]
