#!/usr/bin/env pwsh
# Local quality gate for services/pledges_api: ruff + pytest on Python 3.14 (the
# Lambda runtime). One command, no AWS. Usage:  pwsh ./check.ps1
$ErrorActionPreference = "Stop"

$repo    = $PSScriptRoot
$svc     = Join-Path $repo "services\pledges_api"
$venv    = Join-Path $repo ".venv"
$py      = Join-Path $venv "Scripts\python.exe"
$ruff    = Join-Path $venv "Scripts\ruff.exe"

# 1. Ensure a Python 3.14 venv (pin to the Lambda runtime, not the machine default).
if (-not (Test-Path $py)) {
    Write-Host "Creating .venv with Python 3.14..." -ForegroundColor Cyan
    py -3.14 -m venv $venv
}

# 2. Install / refresh the gate dependencies.
& $py -m pip install -q --upgrade pip
& $py -m pip install -q -r (Join-Path $svc "requirements-dev.txt")

$pyVersion = (& $py --version)
Write-Host "Using $pyVersion" -ForegroundColor DarkGray

# 3. Lint.
Write-Host "== ruff ==" -ForegroundColor Cyan
& $ruff check (Join-Path $svc "src") (Join-Path $svc "tests")
if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: ruff" -ForegroundColor Red; exit 1 }

# 4. Tests (-rs lists skipped tests with their reason).
Write-Host "== pytest ==" -ForegroundColor Cyan
Push-Location $svc
& $py -m pytest tests/ -q -rs
$testCode = $LASTEXITCODE
Pop-Location
if ($testCode -ne 0) { Write-Host "FAILED: pytest" -ForegroundColor Red; exit 1 }

Write-Host "Quality gate PASSED" -ForegroundColor Green
