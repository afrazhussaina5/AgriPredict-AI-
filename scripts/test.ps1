<#
.SYNOPSIS
  AgriPredict AI - runs every Phase 1 check (tests, lint, type checks, build).
.DESCRIPTION
  Backend : pytest, ruff check, mypy
  Frontend: eslint, tsc --noEmit, vitest, production build
  Exit code 0 means everything passed; anything else prints a failure summary.
.EXAMPLE
  .\scripts\test.ps1
#>

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $Root '.venv\Scripts\python.exe'
$failures = @()

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host ''
    Write-Host "=== $Label ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
        $script:failures += $Label
        Write-Host "--- FAILED: $Label (exit $LASTEXITCODE) ---" -ForegroundColor Red
    }
    else {
        Write-Host "--- passed: $Label ---" -ForegroundColor Green
    }
}

if (-not (Test-Path $venvPython)) {
    Write-Host 'Virtual environment not found. Run .\scripts\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

# ---------------- Backend ----------------
Push-Location (Join-Path $Root 'apps\api')
try {
    Invoke-Step 'backend: pytest' { & $venvPython -m pytest }
    Invoke-Step 'backend: ruff check' { & $venvPython -m ruff check . }
    Invoke-Step 'backend: mypy' { & $venvPython -m mypy app }
    # Validates the migration revision graph without connecting to any database.
    Invoke-Step 'backend: alembic heads' { & $venvPython -m alembic heads }
}
finally {
    Pop-Location
}

# ---------------- Frontend ----------------
Push-Location (Join-Path $Root 'apps\web')
try {
    Invoke-Step 'frontend: lint' { npm run lint }
    Invoke-Step 'frontend: typecheck' { npm run typecheck }
    Invoke-Step 'frontend: unit tests' { npm run test }
    Invoke-Step 'frontend: production build' { npm run build }
}
finally {
    Pop-Location
}

# ---------------- Summary ----------------
Write-Host ''
if ($failures.Count -eq 0) {
    Write-Host 'RESULT: all checks passed.' -ForegroundColor Green
    exit 0
}

Write-Host 'RESULT: FAILED steps:' -ForegroundColor Red
$failures | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
exit 1
