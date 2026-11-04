param([switch]$Foreground)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$pythonPath = Join-Path $backendRoot '.venv/Scripts/python.exe'
$hostRoot = Join-Path $env:LOCALAPPDATA 'RetailFraudResearchHost'
$credentialPath = Join-Path $hostRoot 'production.dpapi'
$pidPath = Join-Path $hostRoot 'host.pid'
$identityPath = Join-Path $hostRoot 'host-process.json'
if (!(Test-Path -LiteralPath $pythonPath)) { throw 'Install the full backend research environment first.' }
if (!(Test-Path -LiteralPath $credentialPath)) { throw 'Production Windows-encrypted credentials are not configured.' }
if (!$Foreground) {
    if (Test-Path -LiteralPath $pidPath) {
        $existingId = [int](Get-Content -LiteralPath $pidPath)
        if (Get-Process -Id $existingId -ErrorAction SilentlyContinue) { throw 'Research host is already running. Use stop-research-host.ps1 first.' }
    }
    $shellPath = (Get-Process -Id $PID).Path
    $child = Start-Process -FilePath $shellPath -ArgumentList @('-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Foreground') -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $hostRoot 'host.log') -RedirectStandardError (Join-Path $hostRoot 'host-errors.log')
    Set-Content -LiteralPath $pidPath -Value $child.Id
    @{ id=$child.Id; startedAtUtc=$child.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content -LiteralPath $identityPath
    Write-Output 'Research host started. Readiness: http://127.0.0.1:8010/api/v1/health/ready'
    exit
}
$encrypted = [Convert]::FromBase64String([IO.File]::ReadAllText($credentialPath))
$plain = [Security.Cryptography.ProtectedData]::Unprotect($encrypted,$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
try { $configuration = [Text.Encoding]::UTF8.GetString($plain) | ConvertFrom-Json }
finally { [Array]::Clear($plain,0,$plain.Length) }
foreach ($name in @('RF_DATABASE_URL','RF_JWT_SECRET')) {
    $value = $configuration.$name
    if (!$value) { throw "Missing required host configuration: $name" }
    [Environment]::SetEnvironmentVariable($name,$value,'Process')
}
$configuration = $null
$env:RF_ENVIRONMENT = 'production'
$env:RF_COOKIE_SECURE = 'true'
$env:RF_ALLOWED_ORIGINS = '["https://frontend-jnda.vercel.app","https://retail-fraud-intelligence-platform.vercel.app"]'
$env:RF_VOLUME_ROOT = $hostRoot
$env:RF_BIND_HOST = '127.0.0.1'
$env:PORT = '8010'
Remove-Item Env:RF_RESEARCH_API_ORIGIN -ErrorAction SilentlyContinue
Push-Location $backendRoot
try { & $pythonPath -m app.hosted; exit $LASTEXITCODE }
finally {
    Pop-Location
    Remove-Item Env:RF_JWT_SECRET -ErrorAction SilentlyContinue
    Remove-Item Env:RF_DATABASE_URL -ErrorAction SilentlyContinue
}
