$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# The installers bring their own Python in `runtime`; a source installation has .venv.
$python = Join-Path $PSScriptRoot 'runtime\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python)) { throw 'Run setup.cmd first.' }
& $python -m pip install -r requirements-gpu.txt
if ($LASTEXITCODE -ne 0) { throw 'GPU dependency installation failed.' }
Write-Host 'CUDA libraries installed for this application. Restart the backend.'
