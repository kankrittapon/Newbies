param(
  [switch]$Persist
)

Write-Host "Configure environment for Newbies app" -ForegroundColor Cyan

$apiToken = Read-Host "Enter API_TOKEN (backend token)"

$lines = @(
  "API_TOKEN=$apiToken"
)

$envPath = Join-Path -Path (Get-Location) -ChildPath ".env"
Set-Content -Path $envPath -Value ($lines -join "`n") -Encoding UTF8
Write-Host ".env written at $envPath" -ForegroundColor Green

if ($Persist) {
  setx API_TOKEN $apiToken | Out-Null
  Write-Host "Persisted API_TOKEN to user environment. Open a new terminal to use it." -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Cyan

