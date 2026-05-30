# Build React and serve UI + API on one port (8000).
# Usage: .\tools\run_web_demo.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "Create venv first: py -3.12 -m venv .venv" -ForegroundColor Red
  exit 1
}

Write-Host "Building React (web/dist)..." -ForegroundColor Cyan
Push-Location web
if (-not (Test-Path "node_modules")) { npm install }
npm run build
Pop-Location

$port = 8000
$busy = netstat -ano | findstr "LISTENING" | findstr ":$port "
if ($busy) {
  Write-Host "Port $port is already in use (leftover server from a previous run)." -ForegroundColor Red
  Write-Host "Free it:  .\tools\stop_web_port.ps1" -ForegroundColor Yellow
  Write-Host "Or use another port:  uvicorn api.main:app --port 8001  →  http://localhost:8001`n" -ForegroundColor DarkGray
  exit 1
}

Write-Host "`nOpen http://localhost:$port (sign in: owner / owner123)" -ForegroundColor Green
Write-Host "API docs: http://localhost:$port/docs`n" -ForegroundColor DarkGray
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port $port
