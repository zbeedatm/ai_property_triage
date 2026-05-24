# Kubernetes env examples

Copy from `docker/examples/*.env.example` into `docker/secrets/`, then run `k8s/scripts/create-secrets.*`.

**Service hostnames differ from Compose** (Compose allows `_` in service names; Kubernetes uses `-`):

| Compose (`docker-compose.yml`) | Kubernetes Service |
|-------------------------------|-------------------|
| `http://rag:8000`             | `http://rag:8000` (same) |
| `http://image_analyser:8000`  | `http://image-analyser:8000` |
| `http://langgraph_agent:8000` | `http://langgraph-agent:8000` |
| `http://n8n:5678`             | `http://n8n:5678` (same) |

### `langgraph.env` for K8s

```env
RAG_PINECONE_URL=http://rag:8000
IMAGE_SERVICE_URL=http://image-analyser:8000
```

### `webui.env` for K8s

```env
N8N_WEBHOOK_URL=http://n8n:5678/webhook/property-triage
FILE_BASE_URL=http://webui:7860
```

When using **Ingress**, set `FILE_BASE_URL` and n8n `WEBHOOK_URL` / `N8N_HOST` to your public URLs (patch `k8s/base/configmap-n8n.yaml` or use Secret `n8n-env`).
