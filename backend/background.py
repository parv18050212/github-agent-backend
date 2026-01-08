"""
Background Job Processing
Handles async analysis jobs
"""
import traceback
from uuid import UUID
from backend.services.analyzer_service import AnalyzerService


def run_analysis_job(project_id: str, job_id: str, repo_url: str, team_name: str = None):
    """
    Background task to run repository analysis
    
    Args:
        project_id: Project UUID as string
        job_id: Job UUID as string
        repo_url: GitHub repository URL
        team_name: Optional team name
    """
    try:
        # Convert string UUIDs to UUID objects
        project_uuid = UUID(project_id)
        job_uuid = UUID(job_id)
        
        # Run analysis
        AnalyzerService.analyze_repository(
            project_id=project_uuid,
            job_id=job_uuid,
            repo_url=repo_url,
            team_name=team_name
        )
        
    except Exception as e:
        print(f"\n❌ Background job failed:")
        print(f"   Project: {project_id}")
        print(f"   Job: {job_id}")
        print(f"   Error: {str(e)}")
        print(f"\n{traceback.format_exc()}")
