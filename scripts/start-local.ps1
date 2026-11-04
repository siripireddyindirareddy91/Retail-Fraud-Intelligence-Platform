param([ValidateSet(5173,5174)][int]$Port = 5174)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$runtimeRoot = Join-Path $projectRoot 'runtime'
$pythonPath = Join-Path $backendRoot '.venv/Scripts/python.exe'
$nodePath = (Get-Command node -ErrorAction Stop).Source
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath (Join-Path $frontendRoot 'node_modules/vite/bin/vite.js'))) { throw 'Install dependencies first; see INSTALLATION_GUIDE.md.' }
New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
foreach ($servicePort in @(8000,$Port)) {
    $socket = [System.Net.Sockets.TcpClient]::new()
    try { $socket.Connect('127.0.0.1',$servicePort); throw "Port $servicePort is in use. Stop the existing service before starting another." }
    catch [System.Net.Sockets.SocketException] { }
    finally { $socket.Dispose() }
}
Push-Location $backendRoot
try {
    & $pythonPath -m app.cli init-local
    if ($LASTEXITCODE -ne 0) { throw 'Local configuration initialization failed.' }
    & $pythonPath -m alembic -c alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }
$processes = @()
try {
    $api = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','app.main:create_app','--factory','--host','127.0.0.1','--port','8000','--no-access-log') -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'api.log') -RedirectStandardError (Join-Path $runtimeRoot 'api-errors.log')
    $processes += @{ id=$api.Id; service='api' }
    $worker = Start-Process -FilePath $pythonPath -ArgumentList @('-m','app.workers.runner') -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'worker.log') -RedirectStandardError (Join-Path $runtimeRoot 'worker-errors.log')
    $processes += @{ id=$worker.Id; service='worker' }
    $vitePath = Join-Path $frontendRoot 'node_modules/vite/bin/vite.js'
    $frontend = Start-Process -FilePath $nodePath -ArgumentList @('"'+$vitePath+'"','--host','127.0.0.1','--port',"$Port",'--strictPort') -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'frontend.log') -RedirectStandardError (Join-Path $runtimeRoot 'frontend-errors.log')
    $processes += @{ id=$frontend.Id; service='frontend' }
    ConvertTo-Json -InputObject @($processes) | Set-Content -LiteralPath (Join-Path $runtimeRoot 'local-services.json') -Encoding utf8
    $ready = $false
    for ($attempt=0; $attempt -lt 120; $attempt++) {
        try { $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health/ready' -TimeoutSec 1; if ($health.status -eq 'ready') { $ready=$true; break } } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (!$ready) { throw 'API did not become ready. Inspect runtime/api-errors.log.' }
    Write-Output "Website: http://127.0.0.1:$Port/dashboard"
    Write-Output 'API docs: http://127.0.0.1:8000/api/v1/docs'
    Write-Output 'Services run in the background. Use scripts/stop-local.ps1 to stop them.'
} catch {
    Write-Error $_
    throw 'Startup did not complete. Use scripts/stop-local.ps1 and inspect runtime logs.'
}

