param(
  [switch]$Persist
)

Write-Host "Configure environment for Newbies app" -ForegroundColor Cyan

$apiToken = Read-Host "Enter API_TOKEN (backend token)"
$sheetKey = Read-Host "Enter SPREADSHEET_KEY (Google Sheet key)"

$lines = @(
  "API_TOKEN=$apiToken",
  "SPREADSHEET_KEY=$sheetKey"
)

$envPath = Join-Path -Path (Get-Location) -ChildPath ".env"
Set-Content -Path $envPath -Value ($lines -join "`n") -Encoding UTF8
Write-Host ".env written at $envPath" -ForegroundColor Green

if ($Persist) {
  setx API_TOKEN $apiToken | Out-Null
  setx SPREADSHEET_KEY $sheetKey | Out-Null
  Write-Host "Persisted API_TOKEN and SPREADSHEET_KEY to user environment. Open a new terminal to use them." -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Cyan

