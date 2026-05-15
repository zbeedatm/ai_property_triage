#!/usr/bin/env sh
# Same behaviour as run-n8n-local.ps1 — host-side n8n must not use host.docker.internal.
set -eu

export N8N_BLOCK_ENV_ACCESS_IN_NODE=false

# Node often resolves "localhost" to ::1; many dev servers listen only on 127.0.0.1.
# Replace only when localhost is the host (not e.g. localhost.docker.internal).
normalize_localhost_host() {
  printf '%s' "$1" | sed \
    -e 's|http://localhost:|http://127.0.0.1:|g' \
    -e 's|https://localhost:|https://127.0.0.1:|g' \
    -e 's|http://localhost/|http://127.0.0.1/|g' \
    -e 's|https://localhost/|https://127.0.0.1/|g' \
    -e 's|http://localhost?|http://127.0.0.1?|g' \
    -e 's|https://localhost?|https://127.0.0.1?|g' \
    -e 's|http://localhost#|http://127.0.0.1#|g' \
    -e 's|https://localhost#|https://127.0.0.1#|g' \
    -e 's|http://localhost$|http://127.0.0.1|g' \
    -e 's|https://localhost$|https://127.0.0.1|g'
}

fix_url() {
  _name="$1"
  _def="$2"
  _val=$(printenv "$_name" 2>/dev/null || true)
  case "$_val" in
    *host.docker.internal*|'')
      export "$_name=$_def"
      echo "  $_name=$_def  (was empty or host.docker.internal — wrong for host-side n8n)" >&2
      ;;
    *)
      _fixed=$(normalize_localhost_host "$_val")
      if [ "$_fixed" != "$_val" ]; then
        export "$_name=$_fixed"
        echo "  $_name=$_fixed  (localhost → 127.0.0.1 to avoid IPv6 ::1)" >&2
      else
        echo "  $_name=$_val" >&2
      fi
      ;;
  esac
}

echo "Layer 3 URL env (host-side n8n):" >&2
fix_url RAG_URL            http://127.0.0.1:8001
fix_url IMAGE_URL          http://127.0.0.1:8002
fix_url GUARDRAILS_URL     http://127.0.0.1:8003
fix_url LANGGRAPH_URL      http://127.0.0.1:8004
fix_url HUMAN_REVIEW_WEBHOOK_URL http://127.0.0.1:9090

echo "N8N_BLOCK_ENV_ACCESS_IN_NODE=false — starting n8n..." >&2
exec n8n start
