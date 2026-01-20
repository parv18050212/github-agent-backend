#!/bin/bash
# Start Celery Worker for HackEval Analysis
# Usage: ./start_worker.sh

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

echo "Starting Celery worker for HackEval..."
echo "Queues: analysis, batch, dlq"
echo "Concurrency: 2 workers"
echo "====================================="

# Start Celery worker
celery -A celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --queues=analysis,batch,dlq \
    --max-tasks-per-child=10 \
    --time-limit=3600 \
    --soft-time-limit=3300 \
    --logfile=logs/celery_worker.log
