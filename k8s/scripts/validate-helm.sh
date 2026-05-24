#!/usr/bin/env bash
# Lint and render the Helm chart (run from repo root).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if ! command -v helm >/dev/null 2>&1; then
  echo "helm not found; install Helm 3.x" >&2
  exit 1
fi

echo "==> helm lint k8s/helm"
helm lint k8s/helm

echo "==> helm template property-triage k8s/helm --namespace property-triage"
OUT="$(helm template property-triage k8s/helm --namespace property-triage)"
COUNT="$(printf '%s\n' "$OUT" | grep -c '^kind:' || true)"
echo "    resources (kind:): $COUNT"

echo "OK"
