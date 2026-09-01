<#
.SYNOPSIS
    One-command setup and launch for the NYC Taxi Trip Prediction project.

.DESCRIPTION
    Creates the virtualenv, installs dependencies, downloads data, trains a
    model, builds the frontend, and serves everything on one port.

    Each stage is skipped if its output already exists, so re-running is cheap.

.EXAMPLE
    ./run.ps1                      # full pipeline, then serve
.EXAMPLE
    ./run.ps1 -Serve               # skip training, serve the existing model
.EXAMPLE
    ./run.ps1 -SampleFrac 0.02     # fast training run for a wiring check
.EXAMPLE
    ./run.ps1 -Port 8100           # when 8000 is already taken
#>
[CmdletBinding()]
param(
    [double] $SampleFrac = 0.06,
    [int]    $Port       = 8000,
    [switch] $Serve,        # skip training and frontend build
    [switch] $SkipTrain,    # keep the existing model, rebuild the frontend
    [switch] $Retrain       # force training even if a model exists
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"

function Write-Stage($text) {
    Write-Host ""
    Write-Host "==> $text" -ForegroundColor Cyan
}

# --- 1. virtualenv -------------------------------------------------------
if (-not (Test-Path $Python)) {
    Write-Stage "Creating virtualenv"
    python -m venv .venv
    & $Python -m pip install --upgrade pip --quiet
    Write-Stage "Installing Python dependencies (a few minutes)"
    & $Python -m pip install -r requirements.txt --quiet
} else {
    Write-Host "virtualenv present" -ForegroundColor DarkGray
}

# --- 2. train ------------------------------------------------------------
$modelPointer = Join-Path $PSScriptRoot "models\latest.json"
$hasModel = Test-Path $modelPointer

if (-not $Serve -and -not $SkipTrain -and (-not $hasModel -or $Retrain)) {
    Write-Stage "Training (downloads ~450 MB on first run)"
    if (-not (Test-Path "$HOME\.kaggle\kaggle.json") -and -not $env:KAGGLE_USERNAME) {
        Write-Host "  No Kaggle credentials found - using the open TLC source." -ForegroundColor Yellow
        Write-Host "  Predictions will be zone-resolution. See docs/02-data-understanding.md." -ForegroundColor Yellow
    }
    & $Python -m nyctaxi.train --sample-frac $SampleFrac
    if ($LASTEXITCODE -ne 0) { throw "Training failed." }

    Write-Stage "Rendering evaluation report and figures"
    & $Python -m nyctaxi.evaluate
} elseif ($hasModel) {
    Write-Host "model present (use -Retrain to rebuild it)" -ForegroundColor DarkGray
} else {
    Write-Host "No model found. Run without -Serve/-SkipTrain to train one." -ForegroundColor Yellow
}

# --- 3. frontend ---------------------------------------------------------
$dist = Join-Path $PSScriptRoot "frontend\dist\index.html"
if (-not $Serve -or -not (Test-Path $dist)) {
    Write-Stage "Building the frontend"
    Push-Location frontend
    try {
        if (-not (Test-Path "node_modules")) { npm install }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "frontend build present" -ForegroundColor DarkGray
}

# --- 4. serve ------------------------------------------------------------
Write-Stage "Serving on http://127.0.0.1:$Port"
Write-Host "    app   http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "    docs  http://127.0.0.1:$Port/docs" -ForegroundColor Green
Write-Host "    Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $Python -m uvicorn nyctaxi.api.main:app --host 127.0.0.1 --port $Port
