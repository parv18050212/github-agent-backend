"""
Frontend-compatible API endpoints
Matches the expected frontend specification
"""
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from typing import Optional, List
from uuid import UUID
import csv
import io

from src.api.backend.crud import ProjectCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD, AnalysisJobCRUD
from src.api.backend.services.frontend_adapter import FrontendAdapter
from src.api.backend.background import run_analysis_job
from src.api.backend.utils.cache import cache, RedisCache

router = APIRouter(prefix="/api", tags=["frontend"])


@router.get("/projects/{project_id}")
async def get_project_detail(project_id: str):
    """Get detailed project evaluation (matches frontend ProjectEvaluation)"""
    try:
        # Check cache first
        cache_key = f"hackeval:project:{project_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Get project
        project = ProjectCRUD.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get related data
        tech_stack = TechStackCRUD.get_tech_stack(project_id)
        issues = IssueCRUD.get_issues(project_id)
        team_members = TeamMemberCRUD.get_team_members(project_id)
        
        # Get report_json if available
        report_json = project.get("report_json")
        
        # Transform to frontend format
        result = FrontendAdapter.transform_project_response(
            project, tech_stack, issues, team_members, report_json
        )
        
        # Cache for 5 minutes (completed projects change rarely)
        if project.get("status") == "completed":
            cache.set(cache_key, result, RedisCache.TTL_MEDIUM)
        
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
        # Check cache (only for unfiltered queries)
        cache_key = f"hackeval:projects:{status}:{tech}:{sort}:{search}"
        if not search:  # Don't cache search queries
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
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
            
            # Count security issues
            issues = IssueCRUD.get_issues(project["id"])
            security_count = len([i for i in issues if i.get("type") == "security"])
            
            item = FrontendAdapter.transform_project_list_item(project, tech_stack, security_count)
            results.append(item)
        
        # Cache for 30 seconds
        if not search:
            cache.set(cache_key, results, RedisCache.TTL_SHORT)
        
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
        # Check cache (only for unfiltered queries)
        cache_key = f"hackeval:leaderboard:{tech}:{sort}:{search}"
        if not search:
            cached_result = cache.get(cache_key)
            if cached_result:
                return cached_result
        
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
            
            item = FrontendAdapter.transform_leaderboard_item(project, tech_stack)
            results.append(item)
        
        # Cache for 30 seconds
        if not search:
            cache.set(cache_key, results, RedisCache.TTL_SHORT)
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard/chart")
async def get_leaderboard_chart():
    """Get leaderboard data for chart visualization"""
    try:
        # Check cache
        cache_key = "hackeval:leaderboard:chart"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
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
        
        # Cache for 1 minute
        cache.set(cache_key, chart_data, 60)
        
        return chart_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_dashboard_stats():
    """Get aggregate statistics for dashboard"""
    try:
        # Check cache
        cache_key = "hackeval:stats"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
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
        
        result = {
            "totalProjects": len(projects),
            "completedProjects": len(completed),
            "pendingProjects": len(in_progress),  # Changed from inProgressProjects
            "averageScore": avg_score,  # Changed from avgScore
            "totalSecurityIssues": total_issues
        }
        
        # Cache for 30 seconds
        cache.set(cache_key, result, RedisCache.TTL_SHORT)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tech-stacks")
async def get_available_technologies():
    """Get list of all technologies used across projects"""
    try:
        # Check cache
        cache_key = "hackeval:tech-stacks"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
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
        
        # Cache for 5 minutes
        cache.set(cache_key, tech_list, RedisCache.TTL_MEDIUM)
        
        return tech_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all related data"""
    try:
        # Delete related data first
        TechStackCRUD.delete_by_project(project_id)
        IssueCRUD.delete_by_project(project_id)
        TeamMemberCRUD.delete_by_project(project_id)
        
        # Delete project
        success = ProjectCRUD.delete_project(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Invalidate caches
        cache.invalidate_project(project_id)
        
        return {"message": "Project deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-upload")
async def batch_upload(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Batch upload projects from CSV file
    Expected CSV columns: teamName, repoUrl, description (optional)
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        
        # Read CSV content
        content = await file.read()
        # Handle BOM (Byte Order Mark) from Excel/Windows
        csv_text = content.decode('utf-8-sig')  # utf-8-sig handles BOM automatically
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Validate headers - support both camelCase and snake_case
        headers = set(csv_reader.fieldnames or [])
        has_camel = {'teamName', 'repoUrl'}.issubset(headers)
        has_snake = {'team_name', 'repo_url'}.issubset(headers)
        
        if not has_camel and not has_snake:
            raise HTTPException(
                status_code=400, 
                detail="CSV missing required columns: teamName/team_name, repoUrl/repo_url"
            )
        
        # Process each row
        queued_jobs = []
        failed_rows = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
            # Support both camelCase and snake_case column names
            team_name = (row.get('teamName') or row.get('team_name') or '').strip()
            repo_url = (row.get('repoUrl') or row.get('repo_url') or '').strip()
            
            if not team_name or not repo_url:
                failed_rows.append({
                    "row": row_num,
                    "error": "Missing teamName or repoUrl"
                })
                continue
            
            # Validate GitHub URL
            if 'github.com' not in repo_url.lower():
                failed_rows.append({
                    "row": row_num,
                    "error": "Invalid GitHub URL"
                })
                continue
            
            try:
                # Check if already exists
                existing = ProjectCRUD.get_project_by_url(repo_url)
                if existing and existing.get("status") in ["analyzing", "completed"]:
                    failed_rows.append({
                        "row": row_num,
                        "teamName": team_name,
                        "repoUrl": repo_url,
                        "error": f"Already {existing.get('status')}"
                    })
                    continue
                
                # Create project
                if existing:
                    project_id = UUID(existing["id"])
                else:
                    project = ProjectCRUD.create_project(
                        repo_url=repo_url,
                        team_name=team_name
                    )
                    project_id = UUID(project["id"])
                
                # Create job
                job = AnalysisJobCRUD.create_job(project_id)
                job_id = UUID(job["id"])
                
                # Queue analysis
                if background_tasks:
                    background_tasks.add_task(
                        run_analysis_job,
                        project_id=str(project_id),
                        job_id=str(job_id),
                        repo_url=repo_url,
                        team_name=team_name
                    )
                
                queued_jobs.append({
                    "row": row_num,
                    "teamName": team_name,
                    "repoUrl": repo_url,
                    "jobId": str(job_id),
                    "projectId": str(project_id)
                })
                
            except Exception as e:
                failed_rows.append({
                    "row": row_num,
                    "teamName": team_name,
                    "repoUrl": repo_url,
                    "error": str(e)
                })
        
        return {
            "success": len(queued_jobs),
            "failed": len(failed_rows),
            "total": len(queued_jobs) + len(failed_rows),
            "queued": queued_jobs,
            "errors": failed_rows,
            "message": f"Successfully queued {len(queued_jobs)} projects, {len(failed_rows)} failed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
