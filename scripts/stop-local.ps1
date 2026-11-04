$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$statePath = Join-Path $projectRoot 'runtime/local-services.json'
if (!(Test-Path -LiteralPath $statePath)) { Write-Output 'No launcher-owned service processes are recorded.'; exit 0 }
$services = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$taskkillPath = Join-Path $env:SystemRoot 'System32/taskkill.exe'
foreach ($service in $services) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $([int]$service.id)"
    if (!$process) { continue }
    # A stale PID must never terminate a process outside this checkout.
    if (!$process.CommandLine -or $process.CommandLine.IndexOf($projectRoot,[System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        Write-Warning "Skipped PID $($service.id): command line does not belong to this checkout."
        continue
    }
    & $taskkillPath /PID $service.id /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Warning "Service $($service.service) could not be stopped." }
}
Set-Content -LiteralPath $statePath -Value '[]' -Encoding utf8
Write-Output 'Launcher-owned services stopped. Database and research artifacts are preserved.'
