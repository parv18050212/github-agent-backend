#!/bin/bash

# Repository Analyzer - Deployment Script
# Usage: ./deploy.sh [environment]

set -e

ENVIRONMENT=${1:-production}
echo "🚀 Deploying Repository Analyzer to $ENVIRONMENT"

# Load environment variables
if [ -f ".env.$ENVIRONMENT" ]; then
    echo "📝 Loading environment variables from .env.$ENVIRONMENT"
    export $(cat .env.$ENVIRONMENT | grep -v '^#' | xargs)
else
    echo "❌ Error: .env.$ENVIRONMENT file not found"
    exit 1
fi

# Validate required environment variables
echo "🔍 Validating environment variables..."
REQUIRED_VARS=("SUPABASE_URL" "SUPABASE_KEY" "OPENAI_API_KEY")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: $var is not set"
        exit 1
    fi
done
echo "✅ All required variables are set"

# Build Docker images
echo "🏗️  Building Docker images..."
docker-compose build --no-cache

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Start new containers
echo "▶️  Starting containers..."
docker-compose up -d

# Wait for API to be healthy
echo "⏳ Waiting for API to be ready..."
RETRY_COUNT=0
MAX_RETRIES=30
until curl -f http://localhost:8000/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "❌ API failed to start"
        docker-compose logs api
        exit 1
    fi
    echo "Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "✅ API is healthy!"

# Show running containers
echo "📦 Running containers:"
docker-compose ps

# Show logs
echo "📋 Recent logs:"
docker-compose logs --tail=50 api

echo ""
echo "🎉 Deployment complete!"
echo "📡 API available at: http://localhost:8000"
echo "📚 Documentation: http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/health"
echo ""
echo "To view logs: docker-compose logs -f api"
echo "To stop: docker-compose down"
