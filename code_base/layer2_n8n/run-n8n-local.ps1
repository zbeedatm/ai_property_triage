# Start n8n on the host with $env.* allowed in workflow expressions.
# Run from this directory:  cd code_base\layer2_n8n  then  .\run-n8n-local.ps1
# Or from repo root:  .\run-n8n-local.ps1  (wrapper at AI_Property_Triage\run-n8n-local.ps1)
#
# .env.example uses host.docker.internal for n8n *inside Docker* reaching the host.
# When n8n runs on Windows/macOS/Linux, that hostname usually fails -> "connection refused".
# This script sets localhost defaults unless you already set real URLs (without host.docker.internal).

$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"

function Set-HostN8nServiceUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Default127
    )
    # Merged view of inherited + process env (GetEnvironmentVariable(..., "Process") misses User/Machine).
    $v = (Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue).Value
    if ([string]::IsNullOrWhiteSpace($v) -or ($v -match "host\.docker\.internal")) {
        Set-Item -Path "Env:$Name" -Value $Default127
        Write-Host "  $Name = $Default127  (was empty or host.docker.internal - wrong for host-side n8n)" -ForegroundColor DarkYellow
        return
    }
    # Node often resolves localhost to ::1; many dev servers listen only on 127.0.0.1 -> ECONNREFUSED ::1:PORT.
    # Normalize only when localhost is the host (not e.g. localhost.docker.internal).
    $normalized = [regex]::Replace($v, '(?i)://localhost(?=:|/|\?|#|$)', '://127.0.0.1')
    if ($normalized -ne $v) {
        Set-Item -Path "Env:$Name" -Value $normalized
        Write-Host "  $Name = $normalized  (localhost -> 127.0.0.1 to avoid IPv6 ::1)" -ForegroundColor DarkGray
        return
    }
    Write-Host "  $Name = $v" -ForegroundColor DarkGray
}

Write-Host "Layer 3 URL env (host-side n8n):" -ForegroundColor Green
Set-HostN8nServiceUrl "RAG_URL"            "http://127.0.0.1:8001"
Set-HostN8nServiceUrl "IMAGE_URL"          "http://127.0.0.1:8002"
Set-HostN8nServiceUrl "GUARDRAILS_URL"    "http://127.0.0.1:8003"
Set-HostN8nServiceUrl "LANGGRAPH_URL"    "http://127.0.0.1:8004"
Set-HostN8nServiceUrl "HUMAN_REVIEW_WEBHOOK_URL" "http://127.0.0.1:9090"

Write-Host "N8N_BLOCK_ENV_ACCESS_IN_NODE=false - starting n8n..." -ForegroundColor Green
n8n start
