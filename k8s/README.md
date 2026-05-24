# Kubernetes (Helm)

Deploy the same stack as `docker-compose.yml` / `docker-compose.ec2.yml` with **Helm only**.  
Docker Compose is unchanged — use Compose for local dev and single-host EC2.

## Layout

```
k8s/
  helm/                 # Helm chart (Chart.yaml, values.yaml, templates/)
  scripts/
    create-secrets.*    # docker/secrets → K8s Secrets + n8n-flow ConfigMap
    validate-helm.*     # helm lint + template (CI / local check)
```

## Prerequisites

- Kubernetes cluster and `kubectl`
- [Helm](https://helm.sh/) 3.x
- Images on a registry (default: `zbeedatm/property-triage-*:latest`, same as `docker-compose.ec2.yml`)
- `docker/secrets/*.env` populated from `docker/examples/`

## Quick start

From the **repository root**:

```bash
# 1. Secrets + flow.json ConfigMap (required before pods become healthy)
./k8s/scripts/create-secrets.sh
# Windows: powershell -File k8s/scripts/create-secrets.ps1

# 2. Install or upgrade
helm upgrade --install property-triage ./k8s/helm \
  --namespace property-triage \
  --create-namespace

# 3. Restart if pods started before secrets existed
kubectl rollout restart deployment -n property-triage --all
```

**Local images** (after `docker compose build`):

```bash
helm upgrade --install property-triage ./k8s/helm \
  --namespace property-triage \
  -f k8s/helm/values-local.yaml
```

**Validate chart** (no cluster required):

```bash
./k8s/scripts/validate-helm.sh
```

## Configuration

| File | Purpose |
|------|---------|
| `helm/values.yaml` | Default images (`zbeedatm/*`), n8n ConfigMap, resources |
| `helm/values-local.yaml` | `ai_property_triage-*` images from Compose build |
| `helm/templates/` | Deployments, Services, PVC, optional Ingress |

Override at install time, e.g.:

```bash
helm upgrade --install property-triage ./k8s/helm \
  --namespace property-triage \
  --set ingress.enabled=true \
  --set ingress.hosts.webui=app.example.com \
  --set n8n.config.webhookUrl=https://n8n.example.com
```

## Secrets (not in the chart)

| Secret / ConfigMap | Source |
|--------------------|--------|
| `webui-env` | `docker/secrets/webui.env` |
| `guardrails-env` | `docker/secrets/guardrails.env` |
| `rag-env` | `docker/secrets/rag.env` |
| `image-env` | `docker/secrets/image.env` |
| `langgraph-env` | `docker/secrets/langgraph.env` |
| `n8n-env` | optional — `docker/secrets/n8n.env` |
| `n8n-flow` | `code_base/layer2_n8n/flow.json` |

Use in-cluster URLs in `webui.env`, e.g. `N8N_WEBHOOK_URL=http://n8n:5678/webhook/property-triage` (see `docker/examples/webui.env.example`).

## In-cluster services

| Service | DNS | Port |
|---------|-----|------|
| n8n | `n8n` | 5678 |
| webui | `webui` | 7860 |
| guardrails | `guardrails` | 8000 |
| rag | `rag` | 8000 |
| image analyser | `image-analyser` | 8000 |
| langgraph | `langgraph-agent` | 8000 |

## Access (port-forward)

```bash
kubectl port-forward svc/webui 7860:7860 -n property-triage
kubectl port-forward svc/n8n 5678:5678 -n property-triage
```

Or enable Ingress: `--set ingress.enabled=true` (requires an Ingress controller).

## n8n

- PVC `n8n-data` persists workflow data.
- Init container imports `flow.json` once (same as Compose).
- Add **Google Gemini** credentials in the n8n UI after first deploy.

## Uninstall

```bash
helm uninstall property-triage -n property-triage
kubectl delete pvc n8n-data -n property-triage   # optional — retains data if omitted
```
