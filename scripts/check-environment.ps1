<#
.SYNOPSIS
  AgriPredict AI - checks whether the required tools are installed.
.DESCRIPTION
  Run this first. It prints an [OK]/[MISSING] line for git, python, node and npm
  and tells you the exact install command for anything missing.
.EXAMPLE
  .\scripts\check-environment.ps1
#>

$ErrorActionPreference = 'Continue'

Write-Host ''
Write-Host 'AgriPredict AI - environment check' -ForegroundColor Cyan
Write-Host '----------------------------------'

function Test-Tool {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$InstallCommand
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        Write-Host "[MISSING] $Name" -ForegroundColor Red
        Write-Host "          install: $InstallCommand" -ForegroundColor Yellow
        return $false
    }

    $output = ''
    try {
        $output = (& $Name --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
    }
    catch {
        $output = ''
    }

    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -or [string]::IsNullOrWhiteSpace($output)) {
        Write-Host "[BROKEN]  $Name - found but not working (exit code $exitCode)." -ForegroundColor Red
        Write-Host "          install: $InstallCommand" -ForegroundColor Yellow
        return $false
    }

    Write-Host "[OK]      $Name - $output" -ForegroundColor Green
    return $true
}

$missing = @()

$gitInstall = 'winget install --id Git.Git --exact --source winget'
$nodeInstall = 'winget install --id OpenJS.NodeJS.LTS --exact --source winget'
$pythonInstall = 'winget install --id Python.Python.3.12 --exact --source winget'

if (-not (Test-Tool -Name 'git' -InstallCommand $gitInstall)) { $missing += 'git (Git for Windows)' }
if (-not (Test-Tool -Name 'node' -InstallCommand $nodeInstall)) { $missing += 'node (Node.js LTS)' }
if (-not (Test-Tool -Name 'npm' -InstallCommand $nodeInstall)) { $missing += 'npm (ships with Node.js)' }

# Python: try `python` first, then the Windows `py` launcher.
$pythonOk = $false
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonOk = Test-Tool -Name 'python' -InstallCommand $pythonInstall
}
if (-not $pythonOk -and (Get-Command py -ErrorAction SilentlyContinue)) {
    $pythonOk = Test-Tool -Name 'py' -InstallCommand $pythonInstall
}
if (-not $pythonOk) { $missing += 'python (3.11 or newer)' }

Write-Host ''
if ($missing.Count -eq 0) {
    Write-Host 'All required tools are available. Next: .\scripts\setup.ps1' -ForegroundColor Green
    exit 0
}

Write-Host ('Missing or broken: ' + ($missing -join ', ')) -ForegroundColor Red
Write-Host 'Install them with the commands above, close and reopen this window, then re-run:' -ForegroundColor Yellow
Write-Host '  .\scripts\check-environment.ps1' -ForegroundColor Yellow
exit 1
