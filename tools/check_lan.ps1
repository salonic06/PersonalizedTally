# Run on the SERVER PC (the one with the database). No admin required.
Write-Host "=== Personalized Tally LAN check ===" -ForegroundColor Cyan

$ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notmatch "^127\." -and $_.PrefixOrigin -ne "WellKnown" } |
  Select-Object -ExpandProperty IPAddress -Unique

if ($ips) {
  Write-Host "`nUse this URL on other laptops (same Wi-Fi):"
  foreach ($ip in $ips) {
    Write-Host "  http://${ip}:5173" -ForegroundColor Green
    Write-Host "  http://${ip}:8000/docs  (API test)" -ForegroundColor DarkGray
  }
} else {
  Write-Host "No LAN IPv4 found. Connect to Wi-Fi and run ipconfig." -ForegroundColor Yellow
}

Write-Host "`nPorts listening (look for 0.0.0.0:5173 and 0.0.0.0:8000):"
netstat -an | Select-String ":5173|:8000"

$listen5173 = netstat -an | Select-String "0\.0\.0\.0:5173|\[::\]:5173"
$listen8000 = netstat -an | Select-String "0\.0\.0\.0:8000|\[::\]:8000"

if (-not $listen5173) {
  Write-Host "`n[!] Port 5173 not on all interfaces — start: cd web; npm run dev" -ForegroundColor Red
}
if (-not $listen8000) {
  Write-Host "[!] Port 8000 not on all interfaces — start API with: --host 0.0.0.0" -ForegroundColor Red
}

if ($listen5173 -and $listen8000) {
  Write-Host "`nOn THIS PC, open the green :5173 URL above. If that works but another laptop times out," -ForegroundColor Yellow
  Write-Host "run tools/open_lan_firewall.ps1 as Administrator on this PC." -ForegroundColor Yellow
}
