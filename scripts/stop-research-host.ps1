$ErrorActionPreference = 'Stop'
$hostRoot = Join-Path $env:LOCALAPPDATA 'RetailFraudResearchHost'
$pidPath = Join-Path $hostRoot 'host.pid'
$identityPath = Join-Path $hostRoot 'host-process.json'
if (!(Test-Path -LiteralPath $pidPath)) { Write-Output 'No research host PID recorded.'; exit }
$hostProcessId = [int](Get-Content -LiteralPath $pidPath)
# Stop only the recorded process tree. This leaves local-development services
# and persisted datasets/models untouched.
$running = Get-Process -Id $hostProcessId -ErrorAction SilentlyContinue
if ($running) {
    if (!(Test-Path -LiteralPath $identityPath)) { throw 'Process identity is not recorded; refusing to stop an unverified PID.' }
    $identity = Get-Content -LiteralPath $identityPath -Raw | ConvertFrom-Json
    if ($identity.id -ne $hostProcessId -or $running.StartTime.ToUniversalTime().ToString('o') -ne $identity.startedAtUtc) { throw 'Process identity changed; refusing to stop a reused PID.' }
    & taskkill.exe /PID $hostProcessId /T /F
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop the recorded research process tree.' }
}
Remove-Item -LiteralPath $pidPath
if (Test-Path -LiteralPath $identityPath) { Remove-Item -LiteralPath $identityPath }
Write-Output 'Research host stopped. Stored results were preserved. Disable its Funnel separately when no longer needed.'
