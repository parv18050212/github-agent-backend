@echo off
echo Starting Celery Workers and Beat Scheduler...
echo (Note: API must be running for these to work)
docker-compose up celery_worker celery_beat
pause
