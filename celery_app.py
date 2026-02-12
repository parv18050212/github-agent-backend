"""
Celery Application Configuration
Distributed task queue for repository analysis jobs
"""
from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Redis broker from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Convert to rediss:// for Upstash Redis (TLS required)
if 'upstash.io' in REDIS_URL:
    REDIS_URL = REDIS_URL.replace('redis://', 'rediss://')
    if '?ssl_cert_reqs=' not in REDIS_URL:
        REDIS_URL = REDIS_URL.rstrip('/') + '?ssl_cert_reqs=required'

# Create Celery app
celery_app = Celery(
    'hackeval',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['celery_worker']
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    result_expires=3600 * 24,  # Keep results for 24 hours
    
    # Timezone
    timezone='UTC',
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3300,  # 55 minutes soft limit
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # One task at a time (sequential processing)
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks
    
    # Acknowledgment
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Re-queue if worker dies
    
    # Disable events to prevent Redis connection spam (Upstash compatibility)
    worker_send_task_events=False,
    task_send_sent_event=False,
    
    # Redis connection settings (fix Upstash TLS issues)
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_pool_limit=None,  # No connection pool limit
)

# Task routes (separate queues)
celery_app.conf.task_routes = {
    'celery_worker.analyze_single_repository_task': {'queue': 'single_analysis'},  # Single repo analysis (dedicated worker)
    'celery_worker.analyze_repository_task': {'queue': 'single_analysis'},  # Single repo analysis (manual triggers)
    'celery_worker.process_batch_sequential': {'queue': 'batch'},
    'celery_worker.move_to_dlq': {'queue': 'dlq'},
    'celery_worker.update_team_health_status': {'queue': 'default'},
}

# Celery Beat Schedule (Periodic Tasks)
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Weekly batch analysis - Every Monday at 9 AM IST
    'weekly-batch-analysis': {
        'task': 'celery_worker.auto_trigger_batch_analysis',
        'schedule': crontab(day_of_week=1, hour=9, minute=0),
        'args': (False,),  # force=False (respect 7-day interval)
    },
    
    # Auto-resume paused batches - Every Monday at 9:05 AM IST (5 minutes after weekly analysis)
    'auto-resume-paused-batches': {
        'task': 'celery_worker.auto_resume_paused_batches',
        'schedule': crontab(day_of_week=1, hour=9, minute=5),
    },
    
    # Retry DLQ jobs - Every night at 2 AM IST
    'retry-dlq-nightly': {
        'task': 'celery_worker.retry_dlq_jobs',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Update team health status - Every 2 hours
    'update-health-status': {
        'task': 'celery_worker.update_team_health_status',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
    },
}

# Timezone for Beat scheduler
celery_app.conf.timezone = 'Asia/Kolkata'  # IST

if __name__ == '__main__':
    celery_app.start()
