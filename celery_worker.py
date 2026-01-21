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

import subprocess

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
        error_msg = str(exc)
        logger.error(f"❌ Analysis failed for {team_name or repo_url}: {error_msg}")
        
        # Check for Git Authentication/Access errors (don't retry these)
        # 1. Check for subprocess.CalledProcessError with return code 128 (Git error)
        is_git_error_128 = isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 128
        
        # 2. Check for textual indicators in error message
        is_auth_error_text = any(s in error_msg for s in [
            "return code 128", 
            "status 128", 
            "exit status 128",
            "CalledProcessError(128",
            "Authentication failed", 
            "could not read Username",
            "could not read Password"
        ])
        
        is_auth_error = is_git_error_128 or is_auth_error_text
        
        if is_auth_error:
            logger.error(f"🛑 Permanent failure detected (Access Denied/Private Repo). Aborting retries for {repo_url}")
            try:
                AnalysisJobCRUD.fail_job(
                    job_id=UUID(job_id),
                    error_message=f"Access Denied: Private Repository or Invalid Credentials. {error_msg}"
                )
            except Exception as e:
                logger.error(f"Failed to update job status: {e}")
            
            # Don't retry, just return
            return {
                'job_id': job_id,
                'status': 'failed',
                'error': f"Access Denied: {error_msg}"
            }

        # Update job status if max retries exceeded
        if self.request.retries >= self.max_retries:
            try:
                AnalysisJobCRUD.fail_job(
                    job_id=UUID(job_id),
                    error_message=f"Max retries exceeded: {error_msg}"
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


@celery_app.task
def auto_trigger_batch_analysis(force: bool = False):
    """
    Automatically trigger batch analysis for all active batches
    Scheduled to run every Monday at 9 AM IST via Celery Beat
    
    Args:
        force: If True, ignore 7-day interval and analyze all teams
    
    Returns:
        dict: Summary of batches processed
    """
    logger.info("="*60)
    logger.info("🔄 Auto-triggering weekly batch analysis")
    logger.info("="*60)
    
    try:
        supabase = get_supabase_admin_client()
        
        # Get all active batches
        batches = supabase.table('batches')\
            .select('id, name, semester, year')\
            .eq('status', 'active')\
            .execute()
        
        if not batches.data:
            logger.info("No active batches found")
            return {'total_batches': 0, 'triggered': 0}
        
        results = {
            'total_batches': len(batches.data),
            'triggered': 0,
            'skipped': 0,
            'failed': 0,
            'batch_details': []
        }
        
        for batch in batches.data:
            batch_id = batch['id']
            batch_name = f"{batch['semester']} {batch['year']}"
            
            logger.info(f"📦 Processing: {batch_name}")
            
            try:
                # Get teams in batch with projects
                teams = supabase.table('teams')\
                    .select('id, team_name, project_id, projects(id, repo_url, status, last_analyzed_at)')\
                    .eq('batch_id', batch_id)\
                    .execute()
                
                if not teams.data or len(teams.data) == 0:
                    logger.info(f"  ⚠️  No teams found in {batch_name}")
                    results['skipped'] += 1
                    continue
                
                # Filter teams that need analysis
                from src.api.backend.routers.analysis import should_allow_reanalysis
                
                repos = []
                for team in teams.data:
                    project = team.get('projects')
                    if not project:
                        continue
                    
                    project_data = project[0] if isinstance(project, list) else project
                    allowed, reason = should_allow_reanalysis(project_data, force=force)
                    
                    if allowed:
                        # Create analysis job
                        job = supabase.table('analysis_jobs').insert({
                            'project_id': project_data['id'],
                            'status': 'queued',
                            'metadata': {'auto_scheduled': True, 'batch_id': batch_id}
                        }).execute()
                        
                        repos.append({
                            'project_id': project_data['id'],
                            'job_id': job.data[0]['id'],
                            'repo_url': project_data.get('repo_url'),
                            'team_name': team['team_name']
                        })
                
                if repos:
                    # Queue batch processing
                    process_batch_sequential.delay(batch_id, repos)
                    logger.info(f"  ✅ Queued {len(repos)} teams for analysis")
                    results['triggered'] += 1
                    results['batch_details'].append({
                        'batch': batch_name,
                        'teams_queued': len(repos)
                    })
                else:
                    logger.info(f"  ⏭️  All teams recently analyzed (within 7-day interval)")
                    results['skipped'] += 1
                    
            except Exception as e:
                logger.error(f"  ❌ Failed to process {batch_name}: {e}")
                results['failed'] += 1
        
        # Send completion notification
        send_completion_notification.delay(results)
        
        logger.info("="*60)
        logger.info(f"✅ Auto-trigger complete: {results['triggered']} batches triggered")
        logger.info("="*60)
        
        return results
        
    except Exception as e:
        logger.error(f"Auto-trigger failed: {e}")
        logger.error(traceback.format_exc())
        return {'error': str(e)}


@celery_app.task
def send_completion_notification(results: dict):
    """
    Send notification when batch analysis completes
    Currently logs to console, can be extended for email/Slack
    
    Args:
        results: Summary dict from auto_trigger_batch_analysis
    
    Returns:
        dict: Notification status
    """
    logger.info("="*60)
    logger.info("📧 Weekly Analysis Summary")
    logger.info("="*60)
    logger.info(f"Total Batches: {results.get('total_batches', 0)}")
    logger.info(f"Triggered: {results.get('triggered', 0)}")
    logger.info(f"Skipped: {results.get('skipped', 0)}")
    logger.info(f"Failed: {results.get('failed', 0)}")
    logger.info("")
    
    for detail in results.get('batch_details', []):
        logger.info(f"  ✓ {detail['batch']}: {detail['teams_queued']} teams queued")
    
    logger.info("="*60)
    
    # TODO: Add email notification
    # Example:
    # from src.api.backend.services.email_service import send_email
    # send_email(
    #     to=os.getenv('ADMIN_NOTIFICATION_EMAIL'),
    #     subject='Weekly Batch Analysis Complete',
    #     body=format_email_body(results)
    # )
    
    return {'notification_sent': True, 'method': 'console_log'}


@celery_app.task
def update_team_health_status():
    """
    Periodic task to update health status for all teams.
    Runs every 2 hours via Celery Beat.
    
    Calculates health status and risk flags based on:
    - Days since last commit
    - Contribution balance
    - Team participation rate
    - Commit velocity trends
    
    Returns:
        dict: Summary of teams updated
    """
    logger.info("="*60)
    logger.info("🏥 Starting Team Health Status Update")
    logger.info("="*60)
    
    try:
        from src.api.backend.utils.health import calculate_team_health
        import json
        
        supabase = get_supabase_admin_client()
        
        # Get all teams with basic info
        teams_response = supabase.table("teams").select(
            "id, team_name, last_activity, created_at"
        ).execute()
        
        teams = teams_response.data or []
        logger.info(f"📊 Processing {len(teams)} teams")
        
        # Get all projects with their report_json (projects have team_id)
        projects_response = supabase.table("projects").select(
            "team_id, report_json"
        ).execute()
        
        # Build a lookup dict: team_id -> report_json
        team_reports = {}
        for project in (projects_response.data or []):
            if project.get("team_id"):
                team_reports[project["team_id"]] = project.get("report_json")
        
        updated = 0
        errors = 0
        health_counts = {"on_track": 0, "at_risk": 0, "critical": 0}
        
        for team in teams:
            try:
                # Get report from lookup (comes from projects table)
                report_json = team_reports.get(team["id"])
                if isinstance(report_json, str):
                    try:
                        report_json = json.loads(report_json)
                    except:
                        report_json = None
                
                # Get member count (assume 4 if not known)
                team_members_count = 4
                if report_json and report_json.get("author_stats"):
                    team_members_count = max(4, len(report_json.get("author_stats", [])))
                
                # Calculate health
                health_status, risk_flags = calculate_team_health(
                    report_json=report_json,
                    team_members_count=team_members_count,
                    last_activity=team.get("last_activity"),
                    created_at=team.get("created_at")
                )
                
                # Update team in database
                supabase.table("teams").update({
                    "health_status": health_status,
                    "risk_flags": risk_flags,
                    "last_health_check": datetime.utcnow().isoformat()
                }).eq("id", team["id"]).execute()
                
                updated += 1
                health_counts[health_status] = health_counts.get(health_status, 0) + 1
                
                if risk_flags:
                    logger.debug(f"  {team['team_name']}: {health_status} - {risk_flags}")
                    
            except Exception as e:
                logger.error(f"Error updating team {team.get('team_name')}: {e}")
                errors += 1
        
        results = {
            "total_teams": len(teams),
            "updated": updated,
            "errors": errors,
            "health_distribution": health_counts
        }
        
        logger.info("="*60)
        logger.info(f"✅ Health update complete:")
        logger.info(f"   On Track: {health_counts.get('on_track', 0)}")
        logger.info(f"   At Risk: {health_counts.get('at_risk', 0)}")
        logger.info(f"   Critical: {health_counts.get('critical', 0)}")
        logger.info(f"   Errors: {errors}")
        logger.info("="*60)
        
        return results
        
    except Exception as e:
        logger.error(f"Health update task failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": str(e)}
