@echo off
echo ========================================
echo GitHub Agent - Docker Compose
echo ========================================
echo.

echo Starting all services...
echo - FastAPI (http://localhost:8000)
echo - Celery Worker
echo - Celery Beat
echo.

docker-compose up --build

pause
