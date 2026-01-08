"""
Frontend-compatible API endpoints
Matches the expected frontend specification
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from uuid import UUID

from backend.crud import ProjectCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD
from backend.services.frontend_adapter import FrontendAdapter

router = APIRouter(prefix="/api", tags=["frontend"])


@router.get("/projects/{project_id}")
async def get_project_detail(project_id: str):
    """Get detailed project evaluation (matches frontend ProjectEvaluation)"""
    try:
        # Get project
        project = ProjectCRUD.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get related data
        tech_stack = TechStackCRUD.get_tech_stack(project_id)
        issues = IssueCRUD.get_issues(project_id)
        team_members = TeamMemberCRUD.get_team_members(project_id)
        
        # Transform to frontend format
        result = FrontendAdapter.transform_project_response(
            project, tech_stack, issues, team_members
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects")
async def list_projects(
    status: Optional[str] = Query(None),
    tech: Optional[str] = Query(None),
    sort: str = Query("recent", pattern="^(recent|score)$"),
    search: Optional[str] = Query(None)
):
    """List all projects with filters (matches frontend ProjectListItem[])""" 
    try:
        projects, _ = ProjectCRUD.list_projects()
        
        # Apply filters
        if status and status != "all":
            projects = [p for p in projects if p.get("status") == status]
        
        if search:
            search_lower = search.lower()
            projects = [p for p in projects 
                       if search_lower in (p.get("team_name") or "").lower() 
                       or search_lower in (p.get("repo_url") or "").lower()]
        
        # Sort
        if sort == "score":
            projects = sorted(projects, key=lambda x: x.get("total_score") or 0, reverse=True)
        else:  # recent
            projects = sorted(projects, key=lambda x: x.get("created_at") or "", reverse=True)
        
        # Transform each project
        results = []
        for project in projects:
            tech_stack = TechStackCRUD.get_tech_stack(project["id"])
            
            # Filter by tech if specified
            if tech:
                tech_names = [t.get("technology") for t in tech_stack]
                if tech not in tech_names:
                    continue
            
            item = FrontendAdapter.transform_project_list_item(project, tech_stack)
            results.append(item)
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard")
async def get_leaderboard(
    tech: Optional[str] = Query(None),
    sort: str = Query("total", pattern="^(total|quality|security|originality|architecture|documentation)$"),
    search: Optional[str] = Query(None)
):
    """Get leaderboard with filters (matches frontend LeaderboardEntry[])""" 
    try:
        projects, _ = ProjectCRUD.list_projects()
        
        # Filter only completed
        projects = [p for p in projects if p.get("status") == "completed"]
        
        # Apply search
        if search:
            search_lower = search.lower()
            projects = [p for p in projects 
                       if search_lower in (p.get("team_name") or "").lower()]
        
        # Sort by score
        score_key = f"{sort}_score" if sort != "total" else "total_score"
        projects = sorted(projects, key=lambda x: x.get(score_key) or 0, reverse=True)
        
        # Transform
        results = []
        for project in projects:
            tech_stack = TechStackCRUD.get_tech_stack(project["id"])
            
            # Filter by tech if specified
            if tech:
                tech_names = [t.get("technology") for t in tech_stack]
                if tech not in tech_names:
                    continue
            
            item = FrontendAdapter.transform_leaderboard_item(project)
            item["techStack"] = [t.get("technology") for t in tech_stack][:5]
            results.append(item)
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard/chart")
async def get_leaderboard_chart():
    """Get leaderboard data for chart visualization"""
    try:
        projects, _ = ProjectCRUD.list_projects()
        completed = [p for p in projects if p.get("status") == "completed"]
        
        # Top 10 by total score
        top_projects = sorted(completed, key=lambda x: x.get("total_score") or 0, reverse=True)[:10]
        
        chart_data = []
        for project in top_projects:
            chart_data.append({
                "teamName": project.get("team_name"),
                "totalScore": project.get("total_score") or 0,
                "qualityScore": project.get("quality_score") or 0,
                "securityScore": project.get("security_score") or 0,
                "originalityScore": project.get("originality_score") or 0,
                "architectureScore": project.get("engineering_score") or 0,
                "documentationScore": project.get("documentation_score") or 0
            })
        
        return chart_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_dashboard_stats():
    """Get aggregate statistics for dashboard"""
    try:
        projects, total_projects = ProjectCRUD.list_projects()
        
        completed = [p for p in projects if p.get("status") == "completed"]
        in_progress = [p for p in projects if p.get("status") in ["pending", "processing"]]
        
        avg_score = 0
        if completed:
            total_scores = sum(p.get("total_score") or 0 for p in completed)
            avg_score = round(total_scores / len(completed), 1)
        
        # Get all tech stacks
        all_tech = set()
        for project in completed:
            tech_stack = TechStackCRUD.get_tech_stack(project["id"])
            for tech in tech_stack:
                tech_name = tech.get("technology")
                if tech_name:
                    all_tech.add(tech_name)
        
        # Count security issues
        total_issues = 0
        for project in completed:
            issues = IssueCRUD.get_issues(project["id"])
            total_issues += len([i for i in issues if i.get("type") == "security"])
        
        return {
            "totalProjects": len(projects),
            "completedProjects": len(completed),
            "inProgressProjects": len(in_progress),
            "averageScore": avg_score,
            "totalTechnologies": len(all_tech),
            "totalSecurityIssues": total_issues,
            "projectsByStatus": {
                "completed": len(completed),
                "processing": len(in_progress),
                "failed": len([p for p in projects if p.get("status") == "failed"])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tech-stacks")
async def get_available_technologies():
    """Get list of all technologies used across projects"""
    try:
        projects, _ = ProjectCRUD.list_projects()
        
        tech_count = {}
        for project in projects:
            tech_stack = TechStackCRUD.get_tech_stack(project["id"])
            for tech in tech_stack:
                name = tech.get("technology")
                if name:
                    tech_count[name] = tech_count.get(name, 0) + 1
        
        # Convert to list and sort by usage
        tech_list = [{"name": name, "count": count} 
                     for name, count in tech_count.items()]
        tech_list = sorted(tech_list, key=lambda x: x["count"], reverse=True)
        
        return tech_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all related data"""
    try:
        # Delete related data first
        TechStackCRUD.delete_by_project(supabase, project_id)
        IssueCRUD.delete_by_project(supabase, project_id)
        TeamMemberCRUD.delete_by_project(supabase, project_id)
        
        # Delete project
        success = ProjectCRUD.delete_project(supabase, project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        
        return {"message": "Project deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
