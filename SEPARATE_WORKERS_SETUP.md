# Separate Celery Workers Setup

## Overview
Created dedicated Celery workers to separate single repository analysis from batch analysis processing.

## Architecture

### Workers

1. **celery_worker_single** (Single Repository Analysis)
   - Container: `github-agent-celery-worker-single`
   - Queue: `single_analysis`
   - Concurrency: 2
   - Purpose: Handles manual "Re-analyze" button clicks from the UI
   - Hostname: `single@<container_id>`

2. **celery_worker_batch** (Batch Analysis)
   - Container: `github-agent-celery-worker-batch`
   - Queues: `batch`, `dlq`, `default`
   - Concurrency: 2
   - Purpose: Handles scheduled batch analysis and background tasks
   - Hostname: `batch@<container_id>`

### Queue Routing

```python
'celery_worker.analyze_repository_task': {'queue': 'single_analysis'}  # Manual triggers
'celery_worker.process_batch_sequential': {'queue': 'batch'}           # Batch processing
'celery_worker.move_to_dlq': {'queue': 'dlq'}                         # Dead letter queue
'celery_worker.update_team_health_status': {'queue': 'default'}       # Health checks
```

## Benefits

1. **Isolation**: Single repo analysis doesn't interfere with batch processing
2. **Scalability**: Can scale workers independently based on load
3. **Monitoring**: Easier to monitor and debug each worker separately
4. **Resource Management**: Can allocate different resources to each worker type

## Deployment

### Start Services
```bash
cd "proj-github agent"
docker compose up -d --build
```

### Monitor Logs

**Single Analysis Worker:**
```bash
docker compose logs -f celery_worker_single
```

**Batch Analysis Worker:**
```bash
docker compose logs -f celery_worker_batch
```

**Both Workers:**
```bash
docker compose logs -f celery_worker_single celery_worker_batch
```

### Check Worker Status
```bash
docker compose ps
```

Expected output:
```
NAME                                  STATUS
github-agent-api                      Up
github-agent-celery-worker-single     Up
github-agent-celery-worker-batch      Up
github-agent-celery-beat              Up
```

## Testing

1. Click "Re-analyze" on a team in the UI
2. Watch the single worker logs:
   ```bash
   docker compose logs -f celery_worker_single
   ```
3. You should see:
   - `Task celery_worker.analyze_repository_task[<task_id>] received`
   - `Starting analysis for <team_name>`
   - `✅ Analysis completed`

## Troubleshooting

### Worker Not Starting
```bash
docker compose logs celery_worker_single
docker compose logs celery_worker_batch
```

### Task Not Being Picked Up
1. Check if worker is running: `docker compose ps`
2. Check queue routing in `celery_app.py`
3. Verify Redis connection in worker logs

### Restart Workers
```bash
docker compose restart celery_worker_single celery_worker_batch
```

## Files Modified

1. `docker-compose.yml` - Added two separate worker services
2. `celery_app.py` - Updated task routing to use `single_analysis` queue
3. `monitor_logs.bat` - Updated to monitor both workers
4. `monitor_logs.ps1` - Updated to monitor both workers
