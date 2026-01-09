"""
Analysis Router
Endpoints for triggering and monitoring repository analysis
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from uuid import UUID
from typing import Dict, Any

from src.api.backend.schemas import (
    AnalyzeRepoRequest,
    AnalyzeRepoResponse,
    AnalysisStatusResponse,
    AnalysisResultResponse,
    ScoreBreakdown,
    TechStackItem,
    IssueItem,
    TeamMemberItem,
    ErrorResponse
)
from src.api.backend.crud import ProjectCRUD, AnalysisJobCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD
from src.api.backend.background import run_analysis_job

router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post(
    "/analyze-repo",
    response_model=AnalyzeRepoResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse}
    }
)
async def analyze_repo(request: AnalyzeRepoRequest, background_tasks: BackgroundTasks):
    """
    Trigger repository analysis
    
    - **repo_url**: GitHub repository URL
    - **team_name**: Optional team or project name
    
    Returns job_id to track analysis progress
    """
    try:
        # Check if repo already exists
        existing = ProjectCRUD.get_project_by_url(request.repo_url)
        if existing:
            # Check if already analyzing or completed
            if existing.get("status") in ["analyzing", "completed"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Repository already {existing.get('status')}"
                )
            # If failed or pending, we can re-analyze
            project_id = UUID(existing["id"])
        else:
            # Create new project
            project = ProjectCRUD.create_project(
                repo_url=request.repo_url,
                team_name=request.team_name
            )
            project_id = UUID(project["id"])
        
        # Create analysis job
        job = AnalysisJobCRUD.create_job(project_id)
        job_id = UUID(job["id"])
        
        # Queue background task
        background_tasks.add_task(
            run_analysis_job,
            project_id=str(project_id),
            job_id=str(job_id),
            repo_url=request.repo_url,
            team_name=request.team_name
        )
        
        return AnalyzeRepoResponse(
            job_id=job_id,
            project_id=project_id,
            status="queued",
            message="Analysis queued successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue analysis: {str(e)}"
        )


@router.get(
    "/analysis-status/{job_id}",
    response_model=AnalysisStatusResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_analysis_status(job_id: UUID):
    """
    Get analysis job status and progress
    
    - **job_id**: UUID of the analysis job
    
    Returns current status, progress (0-100), and current stage
    """
    try:
        job = AnalysisJobCRUD.get_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis job not found"
            )
        
        return AnalysisStatusResponse(
            job_id=UUID(job["id"]),
            project_id=UUID(job["project_id"]),
            status=job["status"],
            progress=job["progress"],
            current_stage=job.get("current_stage"),
            error_message=job.get("error_message"),
            started_at=job["started_at"],
            completed_at=job.get("completed_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


# Alias endpoint for frontend compatibility
@router.get(
    "/analysis/{job_id}",
    response_model=AnalysisStatusResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_analysis_status_alias(job_id: UUID):
    """Alias endpoint for /analysis-status/{job_id} for frontend compatibility"""
    return await get_analysis_status(job_id)



@router.get(
    "/analysis-result/{job_id}",
    response_model=AnalysisResultResponse,
    responses={
        404: {"model": ErrorResponse},
        425: {"model": ErrorResponse}
    }
)
async def get_analysis_result(job_id: UUID):
    """
    Get full analysis results
    
    - **job_id**: UUID of the analysis job
    
    Returns complete analysis report with scores, issues, tech stack, etc.
    Only available when analysis is completed.
    """
    try:
        # Get job
        job = AnalysisJobCRUD.get_job(job_id)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis job not found"
            )
        
        # Check if completed
        if job["status"] != "completed":
            raise HTTPException(
                status_code=status.HTTP_425_TOO_EARLY,
                detail=f"Analysis not completed yet. Current status: {job['status']}"
            )
        
        # Get project
        project_id = UUID(job["project_id"])
        project = ProjectCRUD.get_project(project_id)
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        # Get related data
        tech_stack = TechStackCRUD.get_tech_stack(project_id)
        issues = IssueCRUD.get_issues(project_id)
        team_members = TeamMemberCRUD.get_team_members(project_id)
        
        # Build response
        return AnalysisResultResponse(
            project_id=project_id,
            repo_url=project["repo_url"],
            team_name=project.get("team_name"),
            status=project["status"],
            analyzed_at=project.get("analyzed_at"),
            scores=ScoreBreakdown(
                total_score=project.get("total_score"),
                originality_score=project.get("originality_score"),
                quality_score=project.get("quality_score"),
                security_score=project.get("security_score"),
                effort_score=project.get("effort_score"),
                implementation_score=project.get("implementation_score"),
                engineering_score=project.get("engineering_score"),
                organization_score=project.get("organization_score"),
                documentation_score=project.get("documentation_score")
            ),
            total_commits=project.get("total_commits"),
            verdict=project.get("verdict"),
            ai_pros=project.get("ai_pros"),
            ai_cons=project.get("ai_cons"),
            tech_stack=[
                TechStackItem(
                    technology=t["technology"],
                    category=t.get("category")
                ) for t in tech_stack
            ],
            issues=[
                IssueItem(
                    type=i["type"],
                    severity=i["severity"],
                    file_path=i.get("file_path"),
                    description=i["description"],
                    ai_probability=i.get("ai_probability"),
                    plagiarism_score=i.get("plagiarism_score")
                ) for i in issues
            ],
            team_members=[
                TeamMemberItem(
                    name=tm["name"],
                    commits=tm["commits"],
                    contribution_pct=tm.get("contribution_pct")
                ) for tm in team_members
            ],
            viz_url=project.get("viz_url"),
            report_json=project.get("report_json")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis result: {str(e)}"
        )
