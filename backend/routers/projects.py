"""
Projects Router
Endpoints for managing analyzed projects
"""
from fastapi import APIRouter, HTTPException, Query, status
from uuid import UUID
from typing import Optional
import math

from backend.schemas import (
    ProjectListResponse,
    ProjectListItem,
    AnalysisResultResponse,
    ScoreBreakdown,
    TechStackItem,
    IssueItem,
    TeamMemberItem,
    ErrorResponse
)
from backend.crud import ProjectCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD

router = APIRouter(prefix="/api", tags=["Projects"])


@router.get(
    "/projects",
    response_model=ProjectListResponse,
    responses={400: {"model": ErrorResponse}}
)
async def list_projects(
    status: Optional[str] = Query(None, description="Filter by status"),
    min_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum total score"),
    max_score: Optional[float] = Query(None, ge=0, le=100, description="Maximum total score"),
    team_name: Optional[str] = Query(None, description="Filter by team name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
):
    """
    List all analyzed projects with filtering and pagination
    
    - **status**: Filter by status (pending, analyzing, completed, failed)
    - **min_score**: Minimum total score
    - **max_score**: Maximum total score
    - **team_name**: Filter by team name (partial match)
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 100)
    """
    try:
        projects, total = ProjectCRUD.list_projects(
            status=status,
            min_score=min_score,
            max_score=max_score,
            team_name=team_name,
            page=page,
            page_size=page_size
        )
        
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        
        return ProjectListResponse(
            projects=[
                ProjectListItem(
                    id=UUID(p["id"]),
                    repo_url=p["repo_url"],
                    team_name=p.get("team_name"),
                    status=p["status"],
                    total_score=p.get("total_score"),
                    verdict=p.get("verdict"),
                    created_at=p["created_at"],
                    analyzed_at=p.get("analyzed_at")
                ) for p in projects
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {str(e)}"
        )


@router.get(
    "/projects/{project_id}",
    response_model=AnalysisResultResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_project(project_id: UUID):
    """
    Get detailed information about a specific project
    
    - **project_id**: UUID of the project
    """
    try:
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
            detail=f"Failed to get project: {str(e)}"
        )


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}}
)
async def delete_project(project_id: UUID):
    """
    Delete a project and all related data
    
    - **project_id**: UUID of the project to delete
    
    This will cascade delete all related records (jobs, tech_stack, issues, team_members)
    """
    try:
        deleted = ProjectCRUD.delete_project(project_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )
