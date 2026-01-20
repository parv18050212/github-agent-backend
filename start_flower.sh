#!/bin/bash
# Start Flower Monitoring Dashboard
# Usage: ./start_flower.sh
# Access at: http://localhost:5555

cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

echo "Starting Flower monitoring dashboard..."
echo "URL: http://localhost:5555"
echo "====================================="

# Start Flower
celery -A celery_app flower \
    --port=5555 \
    --broker_api=http://localhost:6379
