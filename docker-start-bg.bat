@echo off
echo ========================================
echo GitHub Agent - Docker (Detached Mode)
echo ========================================
echo.

echo Building images...
docker-compose build

echo.
echo Starting services in background...
docker-compose up -d

echo.
echo ======================================== 
echo Services Started!
echo ========================================
echo.
echo - FastAPI: http://localhost:8000
echo - Docs: http://localhost:8000/docs
echo.
echo View logs:
echo   docker-compose logs -f
echo   docker-compose logs -f api
echo   docker-compose logs -f celery_worker
echo   docker-compose logs -f celery_beat
echo.
echo Stop services:
echo   docker-compose down
echo.

pause
