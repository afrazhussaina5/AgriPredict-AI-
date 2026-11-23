<#
.SYNOPSIS
  AgriPredict AI - database verification and Alembic migrations.
.DESCRIPTION
  Modes:
    verify  - read-only check of the configured database. Prints host, port and
              database name only - never a password. Run this FIRST.
    status  - show the current and applied migrations. Changes nothing.
    up      - apply pending migrations. Asks for confirmation.
    down    - revert the most recent migration. Asks for confirmation.
    new     - create a new empty migration file for developer use.

  Safety:
    * Migrations are never applied automatically.
    * A backup is strongly recommended before 'down'.
.EXAMPLE
  .\scripts\migrate.ps1 verify
  .\scripts\migrate.ps1 status
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [ValidateSet('verify', 'status', 'up', 'down', 'new')]
    [string]$Mode = 'verify',

    [Parameter(Mandatory = $false)]
    [string]$Message = 'manual migration'
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root 'apps\api'
$venvPython = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Host 'Virtual environment not found. Run .\scripts\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $ApiDir '.env'))) {
    Write-Host 'apps\api\.env not found.' -ForegroundColor Yellow
    Write-Host 'Copy apps\api\.env.example to apps\api\.env and fill in POSTGRES_DSN.'
    Write-Host 'Nothing was changed.'
    exit 1
}

Push-Location $ApiDir
try {
    switch ($Mode) {
        'verify' {
            Write-Host 'Verifying database target (read-only)...' -ForegroundColor Cyan
            & $venvPython -m scripts.verify_database
            break
        }
        'status' {
            & $venvPython -m alembic current
            & $venvPython -m alembic heads
            break
        }
        'new' {
            & $venvPython -m alembic revision -m $Message
            break
        }
        'up' {
            Write-Host 'Pending migrations will be applied.' -ForegroundColor Yellow
            $answer = Read-Host "Type 'apply' to continue"
            if ($answer -ne 'apply') {
                Write-Host 'Cancelled. Nothing was changed.'
                break
            }
            & $venvPython -m alembic upgrade head
            break
        }
        'down' {
            Write-Host 'The most recent migration will be REVERTED.' -ForegroundColor Yellow
            Write-Host 'Have you taken a backup?' -ForegroundColor Yellow
            $answer = Read-Host "Type 'revert' to continue"
            if ($answer -ne 'revert') {
                Write-Host 'Cancelled. Nothing was changed.'
                break
            }
            & $venvPython -m alembic downgrade -1
            break
        }
    }
}
finally {
    Pop-Location
}