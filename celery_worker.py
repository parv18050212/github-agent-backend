"""
Celery Task Definitions
Background workers for repository analysis
"""
from celery import Task
from celery.utils.log import get_task_logger
from celery_app import celery_app
from uuid import UUID
import traceback
import time
from typing import List, Dict
from datetime import datetime

from src.api.backend.services.analyzer_service import AnalyzerService
from src.api.backend.crud import AnalysisJobCRUD, BatchCRUD
from src.api.backend.database import get_supabase_admin_client

logger = get_task_logger(__name__)


class CallbackTask(Task):
    """Base task with failure callback for DLQ"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails after max retries"""
        logger.error(f"Task {task_id} failed permanently: {exc}")
        logger.error(f"Args: {args}, Kwargs: {kwargs}")
        
        # Move to DLQ
        job_id = kwargs.get('job_id') or (args[1] if len(args) > 1 else None)
        if job_id:
            move_to_dlq.delay(
                job_id=job_id,
                error=str(exc),
                traceback_str=str(einfo)
            )


@celery_app.task(
    bind=True,
    base=CallbackTask,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=1800,  # Max 30 minutes
    retry_jitter=True
)
def analyze_repository_task(
    self,
    project_id: str,
    job_id: str,
    repo_url: str,
    team_name: str = None
):
    """
    Main repository analysis task
    
    Args:
        project_id: Project UUID as string
        job_id: Job UUID as string
        repo_url: GitHub repository URL
        team_name: Optional team name
    
    Returns:
        dict: Analysis results summary
    """
    try:
        logger.info(f"Starting analysis for {team_name or repo_url}")
        logger.info(f"Job ID: {job_id}, Project ID: {project_id}")
        
        # Convert string UUIDs to UUID objects
        project_uuid = UUID(project_id)
        job_uuid = UUID(job_id)
        
        # Update job with Celery task ID
        supabase = get_supabase_admin_client()
        supabase.table('analysis_jobs').update({
            'metadata': {
                'celery_task_id': self.request.id,
                'retry_count': self.request.retries,
                'started_at': datetime.now().isoformat()
            }
        }).eq('id', job_id).execute()
        
        # Run analysis (existing logic)
        AnalyzerService.analyze_repository(
            project_id=project_uuid,
            job_id=job_uuid,
            repo_url=repo_url,
            team_name=team_name
        )
        
        logger.info(f"✅ Analysis completed for {team_name or repo_url}")
        return {
            'job_id': job_id,
            'status': 'completed',
            'team_name': team_name
        }
        
    except Exception as exc:
        logger.error(f"❌ Analysis failed for {team_name or repo_url}: {exc}")
        
        # Update job status if max retries exceeded
        if self.request.retries >= self.max_retries:
            try:
                AnalysisJobCRUD.fail_job(
                    job_id=UUID(job_id),
                    error_message=f"Max retries exceeded: {str(exc)}"
                )
            except Exception as e:
                logger.error(f"Failed to update job status: {e}")
        
        # Retry with exponential backoff
        raise self.retry(exc=exc)


@celery_app.task(bind=True)
def process_batch_sequential(self, batch_id: str, repos: List[Dict[str, str]]):
    """
    Process batch of repositories sequentially
    Maintains sequential processing for GitHub API rate limiting
    
    Args:
        batch_id: Batch UUID as string
        repos: List of dicts with keys: project_id, job_id, repo_url, team_name
    
    Returns:
        dict: Batch processing summary
    """
    logger.info(f"{'='*60}")
    logger.info(f"🚀 Starting Sequential Batch Processing: {len(repos)} repos")
    logger.info(f"   Batch ID: {batch_id}")
    logger.info(f"{'='*60}")
    
    results = {
        'batch_id': batch_id,
        'total': len(repos),
        'queued': 0,
        'failed': 0
    }
    
    try:
        for i, repo in enumerate(repos):
            current_index = i + 1
            team_name = repo.get("team_name", f"Repo {current_index}")
            repo_url = repo.get("repo_url", "")
            project_id = repo.get("project_id")
            job_id = repo.get("job_id")
            
            logger.info(f"[{current_index}/{len(repos)}] 📦 {team_name} | {repo_url}")
            
            # Queue individual analysis task (non-blocking)
            try:
                task_result = analyze_repository_task.delay(
                    project_id, job_id, repo_url, team_name
                )
                
                results['queued'] += 1
                logger.info(f"    ✅ Queued: {team_name} (task_id: {task_result.id})")
                
            except Exception as e:
                results['failed'] += 1
                logger.error(f"    ❌ Failed to queue: {team_name} - {str(e)}")
            
            # Rate limiting delay (2 seconds between queuing tasks)
            if current_index < len(repos):
                logger.info(f"    ⏳ Waiting 2 seconds...")
                time.sleep(2)
        
        logger.info(f"✅ Batch queuing completed: {results['queued']} queued, {results['failed']} failed to queue")
        
        return results
        
    except Exception as exc:
        logger.error(f"Batch processing failed: {exc}")
        logger.error(traceback.format_exc())
        raise


@celery_app.task
def move_to_dlq(job_id: str, error: str, traceback_str: str):
    """
    Move failed job to Dead Letter Queue for manual review
    
    Args:
        job_id: Job UUID as string
        error: Error message
        traceback_str: Full traceback
    """
    logger.warning(f"📬 Moving job {job_id} to DLQ")
    
    try:
        supabase = get_supabase_admin_client()
        
        # Update job with DLQ flag
        supabase.table('analysis_jobs').update({
            'status': 'dlq',
            'error_message': f"DLQ: {error}",
            'metadata': {
                'dlq': True,
                'dlq_timestamp': datetime.now().isoformat(),
                'error_traceback': traceback_str,
                'requires_manual_review': True
            }
        }).eq('id', job_id).execute()
        
        logger.info(f"✅ Job {job_id} moved to DLQ")
        
    except Exception as e:
        logger.error(f"Failed to move job to DLQ: {e}")


@celery_app.task
def retry_dlq_jobs():
    """
    Retry jobs in DLQ (manual trigger only)
    """
    logger.info("🔄 Checking DLQ for retry candidates...")
    
    try:
        supabase = get_supabase_admin_client()
        
        # Get all DLQ jobs
        dlq_jobs = supabase.table('analysis_jobs')\
            .select('id, project_id, metadata')\
            .eq('status', 'dlq')\
            .execute()
        
        if not dlq_jobs.data:
            logger.info("No jobs in DLQ")
            return
        
        logger.info(f"Found {len(dlq_jobs.data)} jobs in DLQ")
        
        for job in dlq_jobs.data:
            job_id = job['id']
            project_id = job['project_id']
            
            # Get project details
            project = supabase.table('projects')\
                .select('repo_url, team_id, teams(team_name)')\
                .eq('id', project_id)\
                .single()\
                .execute()
            
            if project.data:
                repo_url = project.data['repo_url']
                teams_data = project.data.get('teams')
                team_name = teams_data.get('team_name') if isinstance(teams_data, dict) else None
                
                # Reset job status
                supabase.table('analysis_jobs').update({
                    'status': 'queued',
                    'error_message': None,
                    'metadata': {'dlq_retry': True}
                }).eq('id', job_id).execute()
                
                # Queue analysis task
                analyze_repository_task.delay(
                    project_id=project_id,
                    job_id=job_id,
                    repo_url=repo_url,
                    team_name=team_name
                )
                
                logger.info(f"✅ Retrying job {job_id} from DLQ")
        
    except Exception as e:
        logger.error(f"Failed to process DLQ: {e}")
