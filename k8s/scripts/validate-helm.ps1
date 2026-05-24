# Lint and render the Helm chart (run from repo root).
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../.."))

if (-not (Get-Command helm -ErrorAction SilentlyContinue)) {
    throw "helm not found; install Helm 3.x"
}

Write-Host "==> helm lint k8s/helm"
helm lint k8s/helm
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> helm template property-triage k8s/helm --namespace property-triage"
$out = helm template property-triage k8s/helm --namespace property-triage
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$count = ($out | Select-String "^kind:").Count
Write-Host "    resources (kind:): $count"
Write-Host "OK"
