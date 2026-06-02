# Start the stats server + Cloudflare Tunnel for botchwitch.com
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$Root\app\api.py")) { throw "Could not find app at $Root" }

$Cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$Config = Join-Path $PSScriptRoot "cloudflared-config.yml"

if (-not (Test-Path $Cloudflared)) {
    throw "cloudflared not found. Install with: winget install Cloudflare.cloudflared"
}
if (-not (Test-Path $Config)) {
    throw "Missing $Config — run deploy/setup-tunnel.ps1 first"
}

Write-Host "Starting stats server on http://127.0.0.1:8000 ..."
Start-Process -FilePath "python" -ArgumentList "-m", "app.server", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $Root -WindowStyle Minimized

Start-Sleep -Seconds 2
Write-Host "Starting Cloudflare Tunnel (botchwitch.com) ..."
& $Cloudflared tunnel --config $Config run
