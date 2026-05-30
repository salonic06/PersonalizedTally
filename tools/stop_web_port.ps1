# Free port 8000 (or another) if a previous uvicorn/python server is still running.
# Usage: .\tools\stop_web_port.ps1
#        .\tools\stop_web_port.ps1 -Port 8000
param([int]$Port = 8000)

$lines = netstat -ano | findstr "LISTENING" | findstr ":$Port "
if (-not $lines) {
  Write-Host "Port $Port is free." -ForegroundColor Green
  exit 0
}

$pids = @()
foreach ($line in $lines) {
  $parts = ($line -replace '\s+', ' ').Trim().Split(' ')
  $pids += [int]$parts[-1]
}
$pids = $pids | Sort-Object -Unique

foreach ($pid in $pids) {
  $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
  $label = if ($proc) { "$($proc.ProcessName)" } else { "process" }
  Write-Host "Stopping PID $pid ($label) on port $Port..." -ForegroundColor Yellow
  Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1
$still = netstat -ano | findstr "LISTENING" | findstr ":$Port "
if ($still) {
  Write-Host "Port $Port still in use. Close the other terminal or reboot." -ForegroundColor Red
  exit 1
}
Write-Host "Port $Port is free. Run .\tools\run_web_demo.ps1" -ForegroundColor Green
