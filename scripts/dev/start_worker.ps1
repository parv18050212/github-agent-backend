# Start Celery Worker for HackEval Analysis (Windows)
# Usage: .\start_worker.ps1

$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

# Activate virtual environment
& ".\.venv\Scripts\Activate.ps1"

Write-Host "Starting Celery worker for HackEval..." -ForegroundColor Green
Write-Host "Queues: analysis, batch, dlq" -ForegroundColor Cyan
Write-Host "Concurrency: 2 workers" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Yellow

# Start Celery worker
celery -A celery_app worker `
    --loglevel=info `
    --concurrency=2 `
    --queues=analysis,batch,dlq `
    --max-tasks-per-child=10 `
    --time-limit=3600 `
    --soft-time-limit=3300 `
    --logfile=logs/celery_worker.log `
    --pool=solo
