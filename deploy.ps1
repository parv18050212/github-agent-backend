#!/usr/bin/env pwsh
# Repository Analyzer - Windows Deployment Script
# Usage: .\deploy.ps1 -Environment production

param(
    [string]$Environment = "production"
)

Write-Host "🚀 Deploying Repository Analyzer to $Environment" -ForegroundColor Cyan

# Load environment variables
$envFile = ".env.$Environment"
if (Test-Path $envFile) {
    Write-Host "📝 Loading environment variables from $envFile" -ForegroundColor Yellow
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^([^=#]+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
} else {
    Write-Host "❌ Error: $envFile file not found" -ForegroundColor Red
    exit 1
}

# Validate required environment variables
Write-Host "🔍 Validating environment variables..." -ForegroundColor Yellow
$requiredVars = @("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY")
foreach ($var in $requiredVars) {
    if ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($var))) {
        Write-Host "❌ Error: $var is not set" -ForegroundColor Red
        exit 1
    }
}
Write-Host "✅ All required variables are set" -ForegroundColor Green

# Build Docker images
Write-Host "🏗️  Building Docker images..." -ForegroundColor Cyan
docker-compose build --no-cache

# Stop existing containers
Write-Host "🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

# Start new containers
Write-Host "▶️  Starting containers..." -ForegroundColor Green
docker-compose up -d

# Wait for API to be healthy
Write-Host "⏳ Waiting for API to be ready..." -ForegroundColor Yellow
$retryCount = 0
$maxRetries = 30
do {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            break
        }
    } catch {
        $retryCount++
        if ($retryCount -ge $maxRetries) {
            Write-Host "❌ API failed to start" -ForegroundColor Red
            docker-compose logs api
            exit 1
        }
        Write-Host "Waiting... ($retryCount/$maxRetries)" -ForegroundColor Yellow
        Start-Sleep -Seconds 2
    }
} while ($retryCount -lt $maxRetries)

Write-Host "✅ API is healthy!" -ForegroundColor Green

# Show running containers
Write-Host "`n📦 Running containers:" -ForegroundColor Cyan
docker-compose ps

# Show logs
Write-Host "`n📋 Recent logs:" -ForegroundColor Cyan
docker-compose logs --tail=50 api

Write-Host "`n🎉 Deployment complete!" -ForegroundColor Green
Write-Host "📡 API available at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "📚 Documentation: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "🔍 Health check: http://localhost:8000/health" -ForegroundColor Cyan
Write-Host "`nTo view logs: docker-compose logs -f api" -ForegroundColor Yellow
Write-Host "To stop: docker-compose down" -ForegroundColor Yellow
