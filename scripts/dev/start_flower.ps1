# Start Flower Monitoring Dashboard (Windows)
# Usage: .\start_flower.ps1
# Access at: http://localhost:5555

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Starting Flower monitoring dashboard..." -ForegroundColor Green
Write-Host "URL: http://localhost:5555" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Yellow

# Start Flower
celery -A celery_app flower --port=5555
