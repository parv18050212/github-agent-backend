@echo off
echo ========================================
echo Starting Celery Worker + Beat
echo ========================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

echo.
echo Starting Celery (Worker + Beat combined)...
echo Press Ctrl+C to stop
echo.

REM Start Celery with Beat (combined mode for development)
REM --pool=solo: Windows-compatible single-threaded pool
REM --beat: Enable periodic task scheduler
REM -Q: Listen to all queues (analysis, batch, dlq)
celery -A celery_app worker --pool=solo --loglevel=info -Q analysis,batch,dlq --beat

pause
