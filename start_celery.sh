#!/bin/bash
echo "========================================"
echo "Starting Celery Worker + Beat (Linux)"
echo "========================================"
echo

echo "Activating virtual environment..."
source .venv/bin/activate

echo
echo "Starting Celery (Worker + Beat combined)..."
echo "Press Ctrl+C to stop"
echo

# Start Celery with Beat (combined mode for development)
# --beat: Enable periodic task scheduler
# -Q: Listen to all queues (analysis, batch, dlq)
celery -A celery_app worker --loglevel=info -Q analysis,batch,dlq --beat
