<#
.SYNOPSIS
  AgriPredict AI - one-time setup (virtual environment + dependencies).
.DESCRIPTION
  Creates .venv at the repository root, installs backend dependencies from
  apps/api/requirements-dev.txt, and runs npm install in apps/web.
  No credentials are required and none are created.
.EXAMPLE
  .\scripts\setup.ps1
#>

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

Write-Host ''
Write-Host 'AgriPredict AI - setup' -ForegroundColor Cyan
Write-Host '----------------------'

# 1. Verify tools first
& (Join-Path $PSScriptRoot 'check-environment.ps1')
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Setup stopped: install the missing tools listed above, then re-run .\scripts\setup.ps1' -ForegroundColor Red
    exit 1
}

# 2. Choose a working Python launcher (skip the Microsoft Store stub)
$python = $null
foreach ($candidate in @('python', 'py')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        try { $null = (& $candidate --version 2>&1) } catch { continue }
        if ($LASTEXITCODE -eq 0) { $python = $candidate; break }
    }
}
if (-not $python) {
    Write-Host 'Python 3.11+ is required but no working launcher was found.' -ForegroundColor Red
    exit 1
}

# 3. Virtual environment
$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment: $((Join-Path $Root '.venv'))"
    & $python -m venv (Join-Path $Root '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the Python virtual environment.' }
}
else {
    Write-Host 'Virtual environment already exists - reusing it.'
}

# 4. Backend dependencies (bounded versions, includes test/lint tools)
Write-Host 'Installing backend dependencies...'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed.' }
& $venvPython -m pip install -r (Join-Path $Root 'apps\api\requirements-dev.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip install of backend dependencies failed.' }

# 5. Frontend dependencies
Write-Host 'Installing frontend dependencies (this can take a few minutes)...'
Push-Location (Join-Path $Root 'apps\web')
try {
    npm install
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed.' }
}
finally {
    Pop-Location
}

# 6. Local .env files (templates only - no credentials are created)
Write-Host 'Preparing local environment files...'
foreach ($app in @('api', 'web')) {
    $appDir = Join-Path $Root "apps\$app"
    $example = Join-Path $appDir '.env.example'
    $target = Join-Path $appDir '.env'
    if ((Test-Path $example) -and -not (Test-Path $target)) {
        Copy-Item $example $target
        Write-Host "  created apps\$app\.env from the template (empty values only)"
    }
    elseif (Test-Path $target) {
        Write-Host "  apps\$app\.env already exists - left untouched"
    }
}
Write-Host '  Fill in POSTGRES_DSN in apps\api\.env only when you want to connect a database.'

Write-Host ''
Write-Host 'Setup complete.' -ForegroundColor Green
Write-Host 'Open TWO PowerShell windows and run:'
Write-Host '  Window A:  .\scripts\start-backend.ps1'
Write-Host '  Window B:  .\scripts\start-frontend.ps1'
Write-Host 'Then open http://localhost:5173'
Write-Host 'Run all checks any time with:  .\scripts\test.ps1'
Write-Host 'Verify/apply database migrations with:  .\scripts\migrate.ps1 verify'
