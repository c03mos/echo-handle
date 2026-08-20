$ErrorActionPreference = 'Stop'

$HostAddress = if ($env:HANDLE_HOST) { $env:HANDLE_HOST } else { '0.0.0.0' }
$Port = if ($env:HANDLE_PORT) { $env:HANDLE_PORT } else { '8000' }

Write-Host "Starting handle on ${HostAddress}:${Port}"
python -m uvicorn app.main:app --host $HostAddress --port $Port
