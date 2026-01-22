from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status, Depends
from src.api.backend.utils.auth import get_current_user
from src.api.backend.middleware.auth import AuthUser
from uuid import UUID
import math

from src.api.backend.schemas import (
    LeaderboardResponse,
    LeaderboardItem,
    BatchUploadRequest,
    BatchUploadResponse,
    AnalyzeRepoResponse,
    ErrorResponse
)
from src.api.backend.crud import ProjectCRUD, AnalysisJobCRUD
from fastapi import BackgroundTasks
from src.api.backend.background import run_analysis_job

router = APIRouter(prefix="/api", tags=["Leaderboard"])


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    responses={400: {"model": ErrorResponse}}
)
async def get_leaderboard(
    sort_by: str = Query("total_score", description="Field to sort by"),
    order: str = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: str = Query("completed", description="Filter by status"),
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    mentor_id: Optional[str] = Query(None, description="Filter by mentor ID"),
    current_user: Optional[AuthUser] = Depends(get_current_user)
):
    """
    Get ranked projects leaderboard
    
    - **sort_by**: Field to sort by (total_score, originality_score, quality_score, etc.)
    - **order**: Sort order (asc or desc)
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    - **status**: Filter by status (default: completed)
    - **batch_id**: Optional batch filter
    - **mentor_id**: Optional mentor filter
    """
    
    # If user is a mentor, enforce filtering by their ID
    if current_user and current_user.role == "mentor":
        mentor_id = str(current_user.user_id)

    try:
        # Validate sort_by field
        valid_sort_fields = [
            "total_score", "originality_score", "quality_score",
            "security_score", "implementation_score", "effort_score",
            "engineering_score", "organization_score", "documentation_score",
            "analyzed_at", "total_commits"
        ]
        
        if sort_by not in valid_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort_by field. Must be one of: {', '.join(valid_sort_fields)}"
            )
        
        # Validate order
        if order not in ["asc", "desc"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="order must be 'asc' or 'desc'"
            )
        
        # Get leaderboard data
        projects, total = ProjectCRUD.get_leaderboard(
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
            status=status,
            batch_id=batch_id,
            mentor_id=mentor_id
        )
        
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        
        return LeaderboardResponse(
            leaderboard=[
                LeaderboardItem(
                    rank=p.get("rank", idx + 1),
                    id=UUID(p["id"]),
                    repo_url=p["repo_url"],
                    team_name=p.get("team_name"),
                    total_score=p.get("total_score", 0),
                    originality_score=p.get("originality_score"),
                    quality_score=p.get("quality_score"),
                    security_score=p.get("security_score"),
                    implementation_score=p.get("implementation_score"),
                    verdict=p.get("verdict"),
                    analyzed_at=p.get("analyzed_at")
                ) for idx, p in enumerate(projects)
            ],
            total=total,
            page=page,
            page_size=page_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get leaderboard: {str(e)}"
        )


@router.post(
    "/batch-upload",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={400: {"model": ErrorResponse}}
)
async def batch_upload(request: BatchUploadRequest, background_tasks: BackgroundTasks):
    """
    Submit multiple repositories for analysis
    
    - **repos**: List of repositories to analyze (max 50)
    
    Returns list of job_ids for tracking each analysis
    """
    try:
        jobs = []
        
        for repo_request in request.repos:
            # Check if repo already exists
            existing = ProjectCRUD.get_project_by_url(repo_request.repo_url)
            
            if existing and existing.get("status") in ["analyzing", "completed"]:
                # Skip if already analyzing or completed
                continue
            
            if existing:
                project_id = UUID(existing["id"])
            else:
                # Create new project
                project = ProjectCRUD.create_project(
                    repo_url=repo_request.repo_url,
                    team_name=repo_request.team_name
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
                repo_url=repo_request.repo_url,
                team_name=repo_request.team_name
            )
            
            jobs.append(AnalyzeRepoResponse(
                job_id=job_id,
                project_id=project_id,
                status="queued",
                message="Analysis queued"
            ))
        
        return BatchUploadResponse(
            jobs=jobs,
            total=len(jobs),
            message=f"Queued {len(jobs)} repositories for analysis"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process batch upload: {str(e)}"
        )
