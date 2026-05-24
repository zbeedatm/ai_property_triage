#!/usr/bin/env bash
# Create Kubernetes Secrets from docker/secrets/*.env (same files as Docker Compose).
# Run from repository root: ./k8s/scripts/create-secrets.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NS="${K8S_NAMESPACE:-property-triage}"
SECRETS_DIR="${ROOT}/docker/secrets"

apply_env_secret() {
  local name="$1"
  local file="$2"
  if [[ ! -f "$file" ]]; then
    echo "Missing $file — copy from docker/examples/ first." >&2
    exit 1
  fi
  kubectl create secret generic "$name" \
    --from-env-file="$file" \
    -n "$NS" \
    --dry-run=client -o yaml | kubectl apply -f -
  echo "Applied secret/$name"
}

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

FLOW_JSON="${ROOT}/code_base/layer2_n8n/flow.json"
if [[ ! -f "$FLOW_JSON" ]]; then
  echo "Missing $FLOW_JSON" >&2
  exit 1
fi
kubectl create configmap n8n-flow \
  --from-file=flow.json="$FLOW_JSON" \
  -n "$NS" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "Applied configmap/n8n-flow"

apply_env_secret "webui-env" "${SECRETS_DIR}/webui.env"
apply_env_secret "guardrails-env" "${SECRETS_DIR}/guardrails.env"
apply_env_secret "rag-env" "${SECRETS_DIR}/rag.env"
apply_env_secret "image-env" "${SECRETS_DIR}/image.env"
apply_env_secret "langgraph-env" "${SECRETS_DIR}/langgraph.env"

if [[ -f "${SECRETS_DIR}/n8n.env" ]]; then
  apply_env_secret "n8n-env" "${SECRETS_DIR}/n8n.env"
else
  echo "Optional: create ${SECRETS_DIR}/n8n.env with N8N_BASIC_AUTH_PASSWORD to override chart values."
fi

echo "Done. Secrets are in namespace: $NS"
