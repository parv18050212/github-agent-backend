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
import os
from typing import List, Dict
from datetime import datetime
import json

from src.api.backend.services.analyzer_service import AnalyzerService
from src.api.backend.crud import AnalysisJobCRUD, BatchCRUD
from src.api.backend.database import get_supabase_admin_client

import subprocess

logger = get_task_logger(__name__)


def create_snapshot_from_team(team_id: str, run_number: int, batch_run_id: str):
    """
    Create analysis snapshot from team for historical tracking
    Called after each successful analysis to preserve state for 7-day comparisons
    
    Args:
        team_id: UUID of team
        run_number: Analysis run number (1, 2, 3, etc.)
        batch_run_id: UUID of batch_analysis_run
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get current team state (teams table now has all analysis data)
        team = supabase.table('teams').select(
            'report_json, repo_url, batch_id'
        ).eq('id', team_id).execute()
        
        if not team.data:
            logger.warning(f"Team {team_id} not found for snapshot")
            return
        
        team_data = team.data[0]
        report_json = team_data.get('report_json')
        
        # Parse report if string
        if isinstance(report_json, str):
            try:
                report_json = json.loads(report_json)
            except:
                logger.warning(f"Failed to parse report_json for snapshot")
                report_json = {}
        
        # Extract scores from report
        scores = {
            'quality_score': report_json.get('quality', {}).get('score', 0),
            'security_score': report_json.get('security', {}).get('score', 0),
            'architecture_score': report_json.get('architecture', {}).get('score', 0),
            'documentation_score': report_json.get('documentation', {}).get('score', 0),
            'originality_score': report_json.get('originality', {}).get('score', 0),
            'total_score': report_json.get('final_scores', {}).get('total_score', 0)
        }
        
        # Create snapshot
        # Extract additional metrics from report
        commit_count = report_json.get('commit_count', 0)
        file_count = report_json.get('file_count', 0)
        lines_of_code = report_json.get('lines_of_code', 0)
        tech_stack_count = len(report_json.get('tech_stack', [])) if report_json.get('tech_stack') else 0
        issue_count = len(report_json.get('issues', [])) if report_json.get('issues') else 0
        
        snapshot_data = {
            'team_id': team_id,
            'batch_run_id': batch_run_id,
            'run_number': run_number,
            'analyzed_at': datetime.utcnow().isoformat(),
            'quality_score': scores['quality_score'],
            'security_score': scores['security_score'],
            'engineering_score': scores['architecture_score'],  # Map architecture to engineering
            'documentation_score': scores['documentation_score'],
            'originality_score': scores['originality_score'],
            'total_score': scores['total_score'],
            'commit_count': commit_count,
            'file_count': file_count,
            'lines_of_code': lines_of_code,
            'tech_stack_count': tech_stack_count,
            'issue_count': issue_count
        }
        
        supabase.table('analysis_snapshots').insert(snapshot_data).execute()
        logger.info(f"✅ Snapshot created: team={team_id}, run={run_number}")
        
    except Exception as e:
        logger.error(f"Failed to create snapshot: {e}")
        logger.error(traceback.format_exc())


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
    team_id: str,  # Changed from project_id to team_id
    job_id: str,
    repo_url: str,
    team_name: str = None
):
    """
    Main repository analysis task
    
    Args:
        team_id: Team UUID as string (parameter name kept as team_id for clarity)
        job_id: Job UUID as string
        repo_url: GitHub repository URL
        team_name: Optional team name
    
    Returns:
        dict: Analysis results summary
    """
    try:
        logger.info(f"Starting analysis for {team_name or repo_url}")
        logger.info(f"Job ID: {job_id}, Team ID: {team_id}")
        
        # Convert string UUIDs to UUID objects
        team_uuid = UUID(team_id)
        job_uuid = UUID(job_id)
        
        # Check if batch analysis has been paused before starting
        supabase = get_supabase_admin_client()
        
        # Get the batch_id from the job metadata
        job_data = supabase.table('analysis_jobs').select('metadata').eq('id', job_id).execute()
        if job_data.data:
            batch_id = job_data.data[0].get('metadata', {}).get('batch_id')
            if batch_id:
                # Check if this batch's analysis run is paused
                runs_response = supabase.table("batch_analysis_runs")\
                    .select("status")\
                    .eq("batch_id", batch_id)\
                    .order("run_number", desc=True)\
                    .limit(1)\
                    .execute()
                
                if runs_response.data and runs_response.data[0].get("status") == "paused":
                    logger.info(f"⏸️  Batch analysis is paused. Skipping analysis for {team_name or repo_url}")
                    # Update job status to cancelled
                    supabase.table('analysis_jobs').update({
                        'status': 'cancelled',
                        'error_message': 'Batch analysis was paused',
                        'completed_at': datetime.now().isoformat()
                    }).eq('id', job_id).execute()
                    
                    return {
                        'job_id': job_id,
                        'status': 'cancelled',
                        'reason': 'batch_paused'
                    }
        
        # Update job with Celery task ID
        supabase = get_supabase_admin_client()
        supabase.table('analysis_jobs').update({
            'metadata': {
                'celery_task_id': self.request.id,
                'retry_count': self.request.retries,
                'started_at': datetime.now().isoformat()
            }
        }).eq('id', job_id).execute()
        
        # Run analysis (existing logic) - now uses team_id
        AnalyzerService.analyze_repository(
            team_id=team_uuid,  # Changed from project_id to team_id
            job_id=job_uuid,
            repo_url=repo_url,
            team_name=team_name
        )
        
        # CREATE SNAPSHOT after successful analysis (for 7-day tracking)
        try:
            # Get job metadata for run tracking
            job_metadata = supabase.table('analysis_jobs').select('run_number, batch_id, metadata').eq('id', job_id).execute()
            run_number = job_metadata.data[0].get('run_number') if job_metadata.data else None
            batch_run_id = job_metadata.data[0].get('metadata', {}).get('batch_run_id') if job_metadata.data else None
            
            # Create snapshot if we have run tracking info
            if run_number and batch_run_id:
                create_snapshot_from_team(
                    team_id=team_id,
                    run_number=run_number,
                    batch_run_id=batch_run_id
                )
                logger.info(f"📸 Snapshot created for team {team_id}, run {run_number}")
        except Exception as e:
            # Don't fail the job if snapshot creation fails
            logger.warning(f"⚠️ Failed to create snapshot: {e}")
        
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


@celery_app.task(
    bind=True,
    base=CallbackTask,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=1800,  # Max 30 minutes
    retry_jitter=True
)
def analyze_single_repository_task(
    self,
    team_id: str,
    job_id: str,
    repo_url: str,
    team_name: str = None
):
    """
    Single repository analysis task (dedicated worker, not part of batch)
    
    This task is identical to analyze_repository_task but routes to a separate
    queue (single_analysis) with its own dedicated worker. This prevents single
    repository analyses from getting stuck behind batch jobs.
    
    Args:
        team_id: Team UUID as string
        job_id: Job UUID as string
        repo_url: GitHub repository URL
        team_name: Optional team name
    
    Returns:
        dict: Analysis results summary
    """
    try:
        logger.info(f"🔍 [SINGLE] Starting analysis for {team_name or repo_url}")
        logger.info(f"Job ID: {job_id}, Team ID: {team_id}")
        
        # Convert string UUIDs to UUID objects
        team_uuid = UUID(team_id)
        job_uuid = UUID(job_id)
        
        # Update job with Celery task ID
        supabase = get_supabase_admin_client()
        supabase.table('analysis_jobs').update({
            'metadata': {
                'celery_task_id': self.request.id,
                'retry_count': self.request.retries,
                'started_at': datetime.now().isoformat(),
                'worker_type': 'single'
            }
        }).eq('id', job_id).execute()
        
        # Run analysis
        AnalyzerService.analyze_repository(
            team_id=team_uuid,
            job_id=job_uuid,
            repo_url=repo_url,
            team_name=team_name
        )
        
        # CREATE SNAPSHOT after successful analysis (for 7-day tracking)
        try:
            # Get job metadata for run tracking
            job_metadata = supabase.table('analysis_jobs').select('run_number, batch_id, metadata').eq('id', job_id).execute()
            run_number = job_metadata.data[0].get('run_number') if job_metadata.data else None
            batch_run_id = job_metadata.data[0].get('metadata', {}).get('batch_run_id') if job_metadata.data else None
            
            # Create snapshot if we have run tracking info
            if run_number and batch_run_id:
                create_snapshot_from_team(
                    team_id=team_id,
                    run_number=run_number,
                    batch_run_id=batch_run_id
                )
                logger.info(f"📸 Snapshot created for team {team_id}, run {run_number}")
        except Exception as e:
            # Don't fail the job if snapshot creation fails
            logger.warning(f"⚠️ Failed to create snapshot: {e}")
        
        logger.info(f"✅ [SINGLE] Analysis completed for {team_name or repo_url}")
        return {
            'job_id': job_id,
            'status': 'completed',
            'team_name': team_name
        }
        
    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"❌ [SINGLE] Analysis failed for {team_name or repo_url}: {error_msg}")
        
        # Check for Git Authentication/Access errors (don't retry these)
        is_git_error_128 = isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 128
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
        repos: List of dicts with keys: team_id, job_id, repo_url, team_name
    
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
        'failed': 0,
        'paused': False
    }
    
    try:
        supabase = get_supabase_admin_client()
        
        for i, repo in enumerate(repos):
            # Check if batch analysis has been paused
            runs_response = supabase.table("batch_analysis_runs")\
                .select("status")\
                .eq("batch_id", batch_id)\
                .order("run_number", desc=True)\
                .limit(1)\
                .execute()
            
            if runs_response.data and runs_response.data[0].get("status") == "paused":
                logger.info(f"⏸️  Batch analysis paused. Stopping after {i} repos.")
                results['paused'] = True
                break
            
            current_index = i + 1
            team_name = repo.get("team_name", f"Repo {current_index}")
            repo_url = repo.get("repo_url", "")
            team_id = repo.get("team_id")  # Changed from project_id
            job_id = repo.get("job_id")
            
            logger.info(f"[{current_index}/{len(repos)}] 📦 {team_name} | {repo_url}")
            
            # Queue individual analysis task (non-blocking)
            try:
                task_result = analyze_repository_task.delay(
                    team_id, job_id, repo_url, team_name  # Changed from project_id to team_id
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
        
        if results['paused']:
            logger.info(f"⏸️  Batch paused: {results['queued']} queued before pause, {results['failed']} failed to queue")
        else:
            logger.info(f"✅ Batch queuing completed: {results['queued']} queued, {results['failed']} failed to queue")
        
        return results
        
    except Exception as exc:
        logger.error(f"Batch processing failed: {exc}")
        logger.error(traceback.format_exc())
        raise


@celery_app.task(bind=True)
def resume_batch_analysis_task(self, batch_id: str, run_id: str, repos: List[Dict[str, str]]):
    """
    Resume a paused batch analysis
    
    Args:
        batch_id: Batch UUID as string
        run_id: Batch analysis run ID
        repos: List of remaining repos to process
    
    Returns:
        dict: Batch processing summary
    """
    logger.info(f"{'='*60}")
    logger.info(f"▶️  Resuming Batch Analysis: {len(repos)} remaining repos")
    logger.info(f"   Batch ID: {batch_id}")
    logger.info(f"   Run ID: {run_id}")
    logger.info(f"{'='*60}")
    
    # Use the same sequential processing logic
    return process_batch_sequential(batch_id, repos)


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
            .select('id, team_id, metadata')\
            .eq('status', 'dlq')\
            .execute()
        
        if not dlq_jobs.data:
            logger.info("No jobs in DLQ")
            return
        
        logger.info(f"Found {len(dlq_jobs.data)} jobs in DLQ")
        
        for job in dlq_jobs.data:
            job_id = job['id']
            team_id = job['team_id']  # Changed from project_id
            
            # Get team details (teams table now has repo_url)
            team = supabase.table('teams')\
                .select('repo_url, team_name')\
                .eq('id', team_id)\
                .single()\
                .execute()
            
            if team.data:
                repo_url = team.data['repo_url']
                team_name = team.data.get('team_name')
                
                # Reset job status
                supabase.table('analysis_jobs').update({
                    'status': 'queued',
                    'error_message': None,
                    'metadata': {'dlq_retry': True}
                }).eq('id', job_id).execute()
                
                # Queue analysis task
                analyze_repository_task.delay(
                    team_id=team_id,  # Changed from project_id
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
                # Get teams in batch (teams table now has all analysis data)
                teams = supabase.table('teams')\
                    .select('id, team_name, repo_url, status, last_analyzed_at')\
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
                    # Check if team needs analysis
                    allowed, reason = should_allow_reanalysis(team, force=force)
                    
                    if allowed and team.get('repo_url'):
                        # Create analysis job
                        job = supabase.table('analysis_jobs').insert({
                            'team_id': team['id'],  # Changed from project_id
                            'status': 'queued',
                            'metadata': {'auto_scheduled': True, 'batch_id': batch_id}
                        }).execute()
                        
                        repos.append({
                            'team_id': team['id'],  # Changed from project_id
                            'job_id': job.data[0]['id'],
                            'repo_url': team.get('repo_url'),
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
    Send email notification when batch analysis completes
    Sends to all admins and mentors
    
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
    
    # Send email notifications
    try:
        from src.api.backend.utils.email import send_alert_email
        
        supabase = get_supabase_admin_client()
        
        # Get all admins and mentors
        users_response = supabase.table("users").select("email, role").in_("role", ["admin", "mentor"]).execute()
        
        if not users_response.data:
            logger.warning("No admins or mentors found to send notifications")
            return {"status": "skipped", "reason": "no_recipients"}
        
        # Build email body
        email_body = f"""Weekly Batch Analysis Complete

Summary:
--------
Total Batches: {results.get('total_batches', 0)}
Triggered: {results.get('triggered', 0)}
Skipped: {results.get('skipped', 0)}
Failed: {results.get('failed', 0)}

Batch Details:
--------------
"""
        
        for detail in results.get('batch_details', []):
            email_body += f"✓ {detail['batch']}: {detail['teams_queued']} teams analyzed\n"
        
        email_body += f"""

New scores are now available in the dashboard.

View your teams: {os.getenv('FRONTEND_URL', 'http://localhost:5173')}/dashboard

---
This is an automated notification from GitHub Agent Analysis System.
"""
        
        # Send to each user
        sent_count = 0
        failed_count = 0
        
        for user in users_response.data:
            try:
                send_alert_email(
                    subject="Weekly Analysis Complete - New Scores Available",
                    body_text=email_body,
                    to_email=user['email']
                )
                sent_count += 1
                logger.info(f"✓ Email sent to {user['email']} ({user['role']})")
            except Exception as e:
                failed_count += 1
                logger.error(f"✗ Failed to send email to {user['email']}: {e}")
        
        logger.info(f"📧 Email notifications: {sent_count} sent, {failed_count} failed")
        
        return {
            "status": "completed",
            "emails_sent": sent_count,
            "emails_failed": failed_count,
            "total_recipients": len(users_response.data)
        }
        
    except Exception as e:
        logger.error(f"Failed to send email notifications: {e}")
        logger.error(traceback.format_exc())
        return {"status": "failed", "error": str(e)}
    
    return {'notification_sent': True, 'method': 'console_log'}


@celery_app.task
def auto_resume_paused_batches():
    """
    Automatically resume paused batch analyses
    Scheduled to run every Monday at 9:05 AM IST via Celery Beat
    
    This ensures that if an admin paused a batch and forgot to resume it,
    it will automatically resume during the next weekly analysis cycle.
    
    Returns:
        dict: Summary of batches resumed
    """
    logger.info("="*60)
    logger.info("▶️  Auto-resuming paused batch analyses")
    logger.info("="*60)
    
    try:
        supabase = get_supabase_admin_client()
        
        # Get all paused batch analysis runs
        paused_runs = supabase.table('batch_analysis_runs')\
            .select('id, batch_id, run_number, batches(name, semester, year)')\
            .eq('status', 'paused')\
            .execute()
        
        if not paused_runs.data:
            logger.info("No paused batch analyses found")
            return {'total_paused': 0, 'resumed': 0}
        
        results = {
            'total_paused': len(paused_runs.data),
            'resumed': 0,
            'failed': 0,
            'batch_details': []
        }
        
        for run in paused_runs.data:
            run_id = run['id']
            batch_id = run['batch_id']
            run_number = run['run_number']
            batch_info = run.get('batches', {})
            batch_name = f"{batch_info.get('semester', 'Unknown')} {batch_info.get('year', '')}"
            
            logger.info(f"📦 Resuming: {batch_name} (Run #{run_number})")
            
            try:
                # Get all teams that haven't been analyzed yet in this run
                teams_result = supabase.table("teams")\
                    .select("id, team_name, repo_url")\
                    .eq("batch_id", batch_id)\
                    .execute()
                
                teams = teams_result.data or []
                
                # Get jobs that are already completed/failed in this run
                jobs_result = supabase.table("analysis_jobs")\
                    .select("team_id, status")\
                    .eq("metadata->>batch_run_id", run_id)\
                    .execute()
                
                completed_team_ids = set(
                    job["team_id"] for job in (jobs_result.data or [])
                    if job["status"] in ["completed", "failed", "cancelled"]
                )
                
                # Build list of remaining repos to process
                repos = []
                for team in teams:
                    if team["id"] not in completed_team_ids and team.get("repo_url"):
                        # Create new analysis job for this team
                        job_insert = {
                            "team_id": team["id"],
                            "status": "queued",
                            "started_at": datetime.now().isoformat(),
                            "metadata": {
                                "batch_run_id": run_id,
                                "run_number": run_number,
                                "auto_resumed": True
                            }
                        }
                        
                        job_result = supabase.table("analysis_jobs").insert(job_insert).execute()
                        job_id = job_result.data[0]["id"]
                        
                        repos.append({
                            "team_id": team["id"],
                            "job_id": job_id,
                            "repo_url": team["repo_url"],
                            "team_name": team["team_name"]
                        })
                
                if not repos:
                    # No remaining repos to process - mark as completed
                    supabase.table("batch_analysis_runs").update({
                        "status": "completed",
                        "completed_at": datetime.now().isoformat()
                    }).eq("id", run_id).execute()
                    
                    logger.info(f"  ✅ No remaining repos - marked as completed")
                    results['resumed'] += 1
                    results['batch_details'].append({
                        'batch': batch_name,
                        'run_number': run_number,
                        'remaining_repos': 0,
                        'status': 'completed'
                    })
                else:
                    # Update run status to running
                    supabase.table("batch_analysis_runs").update({
                        "status": "running",
                        "metadata": {
                            "auto_resumed_at": datetime.now().isoformat(),
                            "auto_resumed": True
                        }
                    }).eq("id", run_id).execute()
                    
                    # Queue Celery task to process remaining repos
                    task = resume_batch_analysis_task.delay(batch_id, run_id, repos)
                    
                    # Store Celery task ID
                    supabase.table("batch_analysis_runs").update({
                        "metadata": {
                            "celery_task_id": task.id,
                            "auto_resumed_at": datetime.now().isoformat(),
                            "auto_resumed": True
                        }
                    }).eq("id", run_id).execute()
                    
                    logger.info(f"  ✅ Resumed with {len(repos)} remaining repos")
                    results['resumed'] += 1
                    results['batch_details'].append({
                        'batch': batch_name,
                        'run_number': run_number,
                        'remaining_repos': len(repos),
                        'status': 'resumed'
                    })
                    
            except Exception as e:
                logger.error(f"  ❌ Failed to resume {batch_name}: {e}")
                results['failed'] += 1
        
        logger.info("="*60)
        logger.info(f"✅ Auto-resume complete: {results['resumed']} batches resumed")
        logger.info("="*60)
        
        return results
        
    except Exception as e:
        logger.error(f"Auto-resume failed: {e}")
        logger.error(traceback.format_exc())
        return {'error': str(e)}


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
            "id, team_name, last_activity, created_at, report_json"
        ).execute()
        
        teams = teams_response.data or []
        logger.info(f"📊 Processing {len(teams)} teams")
        
        updated = 0
        errors = 0
        health_counts = {"on_track": 0, "at_risk": 0, "critical": 0}
        
        for team in teams:
            try:
                # Get report from team (teams table now has report_json)
                report_json = team.get("report_json")
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
