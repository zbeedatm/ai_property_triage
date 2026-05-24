# Kubernetes deployment (optional)

This directory adds **Kubernetes** manifests for the same stack as `docker-compose.yml` / `docker-compose.ec2.yml`.  
**Docker Compose is unchanged** — use Compose for local dev and single-host EC2; use K8s when you have a cluster.

## Prerequisites

- A Kubernetes cluster (EKS, GKE, AKS, minikube, kind, k3s, …)
- `kubectl` and `kustomize` (built into `kubectl apply -k`)
- Images on a registry (default: `zbeedatm/property-triage-*:latest`, same as `docker-compose.ec2.yml`)
- Secrets created from `docker/secrets/*.env` (see below)

## Quick start

From the **repository root**:

```bash
# 1. Apply Deployments, Services, PVC, n8n ConfigMap (static env)
kubectl apply -k k8s/overlays/default

# 2. Create Secrets + n8n-flow ConfigMap from docker/secrets/ and code_base/layer2_n8n/flow.json
./k8s/scripts/create-secrets.sh          # Linux/macOS
# or
pwsh k8s/scripts/create-secrets.ps1      # Windows

# 3. Restart pods if they were waiting for secrets / flow ConfigMap
kubectl rollout restart deployment -n property-triage --all
```

## Layout

```
k8s/
  base/                 # Shared manifests (Deployments, Services, PVC, n8n init)
  overlays/
    default/            # Docker Hub images (zbeedatm/...)
    local-images/       # Use images built via docker compose (imagePullPolicy: IfNotPresent)
  scripts/              # Helper to sync docker/secrets → K8s Secrets
```

## Services and ports (in-cluster)

| Service          | DNS name (namespace)     | Port |
|------------------|--------------------------|------|
| n8n              | `n8n.property-triage`    | 5678 |
| webui            | `webui`                  | 7860 |
| guardrails       | `guardrails`             | 8000 |
| rag              | `rag`                    | 8000 |
| image_analyser   | `image-analyser`         | 8000 |
| langgraph_agent  | `langgraph-agent`        | 8000 |

n8n env vars use the same internal URLs as Compose: `http://rag:8000`, etc.

## Secrets

Kubernetes expects Secrets named:

- `webui-env`, `guardrails-env`, `rag-env`, `image-env`, `langgraph-env`
- `n8n-env` (optional; only `N8N_BASIC_AUTH_PASSWORD` — other n8n settings are in ConfigMap)

Create them from `docker/secrets/` with the provided scripts, or manually:

```bash
kubectl create secret generic webui-env \
  --from-env-file=docker/secrets/webui.env \
  -n property-triage --dry-run=client -o yaml | kubectl apply -f -
```

Ensure `webui.env` uses in-cluster URLs, e.g. `N8N_WEBHOOK_URL=http://n8n:5678/webhook/property-triage` (see `docker/examples/webui.env.example`).

## Ingress (optional)

Apply after installing an Ingress controller (nginx, Traefik, AWS Load Balancer Controller):

```bash
kubectl apply -f k8s/base/ingress.yaml
```

Edit hostnames in `ingress.yaml` before use. Set n8n `WEBHOOK_URL` / `N8N_HOST` to match your public URL.

## Local images (built with Compose)

After `docker compose build`:

```bash
kubectl apply -k k8s/overlays/local-images
```

This overlay retags Deployments to `ai_property_triage-*:latest` (Compose project name) and sets `imagePullPolicy: IfNotPresent` for kind/minikube.

## n8n

- **PVC** `n8n-data` persists workflow DB and credentials.
- **Init container** imports `flow.json` once (same logic as Compose entrypoint).
- Configure **Google Gemini** credentials in the n8n UI after first deploy.

## Access without Ingress (port-forward)

```bash
kubectl port-forward svc/webui 7860:7860 -n property-triage
kubectl port-forward svc/n8n 5678:5678 -n property-triage
```

## Uninstall

```bash
kubectl delete -k k8s/overlays/default
# PVC is retained unless you delete it:
kubectl delete pvc n8n-data -n property-triage
```
