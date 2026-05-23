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

$env:PT_SERVE_WEB = "1"
Write-Host "`nOpen http://localhost:8000 (sign in: owner / owner123)" -ForegroundColor Green
Write-Host "API docs: http://localhost:8000/docs`n" -ForegroundColor DarkGray
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
