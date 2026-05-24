# Kubernetes env examples

Copy from `docker/examples/*.env.example` into `docker/secrets/`, then run `k8s/scripts/create-secrets.*`.

For **Ingress**, set public URLs in Helm values or `docker/secrets/webui.env`:

- `N8N_WEBHOOK_URL` → your public n8n webhook base
- n8n: `--set n8n.config.webhookUrl=...` and `n8n.config.host=...`

Service DNS names use hyphens (`image-analyser`, `langgraph-agent`), not Compose underscore hostnames.
