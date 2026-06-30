# Launch the Suez Port CAD & Masterplan Design engine
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venv = Join-Path $root ".venv"

if (-not (Test-Path $venv)) {
    Write-Host "Creating venv (Python 3.12)..." -ForegroundColor Cyan
    uv venv $venv --python 3.12
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
uv pip install -r (Join-Path $root "requirements.txt") --python (Join-Path $venv "Scripts\python.exe")

Write-Host "Starting server at http://127.0.0.1:8077 ..." -ForegroundColor Green
& (Join-Path $venv "Scripts\python.exe") -m uvicorn main:app --app-dir (Join-Path $root "backend") --host 127.0.0.1 --port 8077 --reload
