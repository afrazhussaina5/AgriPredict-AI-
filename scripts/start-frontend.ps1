<#
.SYNOPSIS
  AgriPredict AI - starts the React frontend on http://localhost:5173
.EXAMPLE
  .\scripts\start-frontend.ps1
#>

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$webDir = Join-Path $Root 'apps\web'

if (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
    Write-Host 'Frontend dependencies not found. Run .\scripts\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

Write-Host 'Starting frontend: http://localhost:5173' -ForegroundColor Cyan
Write-Host 'API calls to /api are proxied to the backend on port 8000.' -ForegroundColor Cyan
Write-Host 'Press Ctrl+C to stop.' -ForegroundColor Yellow

Push-Location $webDir
try {
    npm run dev
}
finally {
    Pop-Location
}
