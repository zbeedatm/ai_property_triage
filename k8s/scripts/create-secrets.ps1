# Create Kubernetes Secrets from docker/secrets/*.env (same files as Docker Compose).
# Run from repository root: pwsh k8s/scripts/create-secrets.ps1

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "../..")
$Ns = if ($env:K8S_NAMESPACE) { $env:K8S_NAMESPACE } else { "property-triage" }
$SecretsDir = Join-Path $Root "docker/secrets"

function Apply-EnvSecret {
    param([string]$Name, [string]$File)
    if (-not (Test-Path $File)) {
        throw "Missing $File — copy from docker/examples/ first."
    }
    kubectl create secret generic $Name `
        --from-env-file=$File `
        -n $Ns `
        --dry-run=client -o yaml | kubectl apply -f -
    Write-Host "Applied secret/$Name"
}

kubectl get namespace $Ns 2>$null
if ($LASTEXITCODE -ne 0) {
    kubectl create namespace $Ns
}

$FlowJson = Join-Path $Root "code_base/layer2_n8n/flow.json"
if (-not (Test-Path $FlowJson)) {
    throw "Missing $FlowJson"
}
kubectl create configmap n8n-flow `
    --from-file="flow.json=$FlowJson" `
    -n $Ns `
    --dry-run=client -o yaml | kubectl apply -f -
Write-Host "Applied configmap/n8n-flow"

Apply-EnvSecret "webui-env" (Join-Path $SecretsDir "webui.env")
Apply-EnvSecret "guardrails-env" (Join-Path $SecretsDir "guardrails.env")
Apply-EnvSecret "rag-env" (Join-Path $SecretsDir "rag.env")
Apply-EnvSecret "image-env" (Join-Path $SecretsDir "image.env")
Apply-EnvSecret "langgraph-env" (Join-Path $SecretsDir "langgraph.env")

$n8nEnv = Join-Path $SecretsDir "n8n.env"
if (Test-Path $n8nEnv) {
    Apply-EnvSecret "n8n-env" $n8nEnv
} else {
    Write-Host "Optional: create docker/secrets/n8n.env with N8N_BASIC_AUTH_PASSWORD to override ConfigMap default."
}

Write-Host "Done. Secrets are in namespace: $Ns"
