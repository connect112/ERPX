<#
.SYNOPSIS
    One-command recovery for the ERPX local stack on Windows (Podman + WSL2).

.DESCRIPTION
    Idempotent: safe to run any time (after a reboot, after WSL sleeps, or just
    to check status). It will:
      1. Fix ComSpec + put the user-scoped Node.js on PATH for this run.
      2. Ensure the Podman machine is running (starts it if stopped).
      3. Start the infra containers and wait for Postgres to report healthy.
      4. Start the API + Celery containers (restart:unless-stopped brings them
         back automatically once the machine is up, but this guarantees it).
      5. Wait for the API health endpoint to return 200.
      6. Start the Vite web dev server (native on the host, NOT a container) in
         its own window if it isn't already listening on 5173.
      7. Print access URLs and the seeded superadmin credentials.

    Why a script and not just `restart:unless-stopped`: the Podman *machine*
    does not auto-start on Windows login, and the web frontend runs as a native
    `npm run dev` process (no container) so nothing restarts it for you.

.NOTES
    Non-destructive. Does not build images, run migrations, or reset data —
    those already happened on first setup. See docs/windows-runbook.md.
#>

$ErrorActionPreference = "Stop"
$RepoRoot = $PSScriptRoot
$NodeDir  = "C:\Users\MSDC-KLB61\AppData\Local\Microsoft\WinGet\Packages\OpenJS.NodeJS.LTS_Microsoft.Winget.Source_8wekyb3d8bbwe\node-v24.19.0-win-x64"
$ApiHealthUrl = "http://localhost:8000/api/v1/health"
$WebUrl = "http://localhost:5173"

$Infra = @("erpx_postgres", "erpx_redis", "erpx_minio", "erpx_elasticsearch")
$App   = @("erpx_api", "erpx_celery_worker", "erpx_celery_beat")

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }

# --- 1. Environment ---------------------------------------------------------
$env:ComSpec = "C:\Windows\System32\cmd.exe"
if (Test-Path $NodeDir) { $env:Path = "$NodeDir;$env:Path" }

# --- 2. Podman machine ------------------------------------------------------
Write-Step "Checking Podman machine"
$machine = podman machine list --format "{{.Name}} {{.Running}}" 2>$null
if ($machine -notmatch "true") {
    Write-Warn "Machine not running - starting it (this can take ~30s)..."
    podman machine start | Out-Null
} else {
    Write-Ok "Podman machine already running"
}

# A running machine can still have a cold API socket after WSL sleep; poke it.
$null = podman ps 2>$null

# --- 3. Infra containers ----------------------------------------------------
Write-Step "Starting infrastructure (postgres, redis, minio, elasticsearch)"
podman start $Infra 2>$null | Out-Null

Write-Host "    waiting for postgres to report healthy..." -NoNewline
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    $s = (podman inspect --format "{{.State.Health.Status}}" erpx_postgres 2>$null)
    if ($s -eq "healthy") { $healthy = $true; break }
    Write-Host "." -NoNewline
}
Write-Host ""
if ($healthy) { Write-Ok "Postgres healthy" } else { Write-Warn "Postgres not healthy yet - API may take longer" }

# --- 4. App containers ------------------------------------------------------
Write-Step "Starting API + Celery (api, celery_worker, celery_beat)"
podman start $App 2>$null | Out-Null
Write-Ok "App containers started"

# --- 5. API health ----------------------------------------------------------
Write-Step "Waiting for API health endpoint"
Write-Host "    " -NoNewline
$apiUp = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri $ApiHealthUrl -UseBasicParsing -TimeoutSec 4
        if ($r.StatusCode -eq 200) { $apiUp = $true; break }
    } catch { }
    Start-Sleep -Seconds 2
    Write-Host "." -NoNewline
}
Write-Host ""
if ($apiUp) { Write-Ok "API responding 200 at $ApiHealthUrl" } else { Write-Warn "API not responding yet - check: podman logs erpx_api" }

# --- 6. Web dev server (native) --------------------------------------------
Write-Step "Checking web dev server (Vite, native host process)"
$webListening = Test-NetConnection -ComputerName localhost -Port 5173 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($webListening) {
    Write-Ok "Web already listening on 5173"
} else {
    Write-Warn "Web not running - launching 'npm run dev' in a new window"
    $webDir = Join-Path $RepoRoot "apps\web"
    # Launch in its own persistent PowerShell window so it survives after this
    # script exits and its Vite logs stay visible.
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "`$env:ComSpec='C:\Windows\System32\cmd.exe'; `$env:Path='$NodeDir;' + `$env:Path; Set-Location '$webDir'; npm run dev"
    )
    Write-Ok "Web dev server launching (allow a few seconds to boot)"
}

# --- 7. Summary -------------------------------------------------------------
Write-Step "ERPX stack summary"
podman ps --format "table {{.Names}}`t{{.Status}}"
Write-Host ""
Write-Host "  Web app   : $WebUrl" -ForegroundColor White
Write-Host "  API docs  : http://localhost:8000/api/docs" -ForegroundColor White
Write-Host "  Login     : admin@erpx.example.com / Admin@12345" -ForegroundColor White
Write-Host ""
