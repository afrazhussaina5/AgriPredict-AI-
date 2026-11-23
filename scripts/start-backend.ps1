<#
.SYNOPSIS
  AgriPredict AI - starts the FastAPI backend on http://127.0.0.1:8000
.EXAMPLE
  .\scripts\start-backend.ps1
#>

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host 'Virtual environment not found. Run .\scripts\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

Write-Host 'Starting backend: http://127.0.0.1:8000  (API docs: /docs)' -ForegroundColor Cyan
Write-Host 'Health check:     http://127.0.0.1:8000/api/v1/health' -ForegroundColor Cyan
Write-Host 'Press Ctrl+C to stop.' -ForegroundColor Yellow

Push-Location (Join-Path $Root 'apps\api')
try {
    & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
}
finally {
    Pop-Location
}
