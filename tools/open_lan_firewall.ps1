# Run as Administrator on the SERVER PC (right-click PowerShell → Run as administrator).
# Allows other laptops on the same private network to reach the dev servers.

$ErrorActionPreference = "Stop"
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "Re-run this script as Administrator." -ForegroundColor Red
  exit 1
}

function Add-PortRule($Name, $Port) {
  $existing = Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
  if ($existing) {
    Write-Host "Rule already exists: $Name"
    return
  }
  New-NetFirewallRule -DisplayName $Name -Direction Inbound -Action Allow -Protocol TCP `
    -LocalPort $Port -Profile Private,Public -ErrorAction Stop | Out-Null
  Write-Host "Added firewall rule: $Name (TCP $Port, Private + Public)" -ForegroundColor Green
}

Add-PortRule "PersonalizedTally Web 5173" 5173
Add-PortRule "PersonalizedTally API 8000" 8000

Write-Host "`nTip: Settings → Network → Wi-Fi → your network → set profile to Private (easier than Public rules)." -ForegroundColor Yellow

Write-Host "`nDone. Restart uvicorn and npm run dev, then run: .\tools\check_lan.ps1" -ForegroundColor Cyan
