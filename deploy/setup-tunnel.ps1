# One-time setup: Cloudflare login, create tunnel, route DNS, write config.
$ErrorActionPreference = "Stop"
$Cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$TunnelName = "botchwitch"
$Domain = "botcwitch.com"
$ConfigTemplate = Join-Path $PSScriptRoot "cloudflared-config.yml"
$Cert = Join-Path $env:USERPROFILE ".cloudflared\cert.pem"

if (-not (Test-Path $Cloudflared)) {
    throw "Install cloudflared first: winget install Cloudflare.cloudflared"
}

if (-not (Test-Path $Cert)) {
    Write-Host ""
    Write-Host "=== Cloudflare login required ==="
    Write-Host "A browser window will open. Log in and authorize botchwitch.com."
    Write-Host ""
    & $Cloudflared tunnel login
}

Write-Host "Creating tunnel '$TunnelName' ..."
$createOut = & $Cloudflared tunnel create $TunnelName 2>&1 | Out-String
Write-Host $createOut

$tunnelList = & $Cloudflared tunnel list 2>&1 | Out-String
if ($tunnelList -notmatch $TunnelName) {
    throw "Tunnel '$TunnelName' was not created. Output:`n$tunnelList"
}

# Parse tunnel UUID from `tunnel list` (second column)
$id = ($tunnelList -split "`n" | Where-Object { $_ -match $TunnelName } | Select-Object -First 1) `
    -replace '\s+', ' ' -split ' ' | Where-Object { $_ -match '^[0-9a-f-]{36}$' } | Select-Object -First 1
if (-not $id) {
    $info = & $Cloudflared tunnel info $TunnelName 2>&1 | Out-String
    if ($info -match '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})') {
        $id = $Matches[1]
    }
}
if (-not $id) { throw "Could not read tunnel ID for '$TunnelName'" }

Write-Host "Tunnel ID: $id"
Write-Host "Routing DNS for $Domain and www.$Domain ..."
& $Cloudflared tunnel route dns $TunnelName $Domain
& $Cloudflared tunnel route dns $TunnelName "www.$Domain"

$config = Get-Content $ConfigTemplate -Raw
$config = $config -replace 'TUNNEL_ID', $id
$config | Set-Content $ConfigTemplate -Encoding utf8

Write-Host ""
Write-Host "Done. Config updated at $ConfigTemplate"
Write-Host "Run: powershell -ExecutionPolicy Bypass -File deploy\start-public.ps1"
