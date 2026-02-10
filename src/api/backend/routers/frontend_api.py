"""
Frontend-compatible API endpoints
Matches the expected frontend specification
"""
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, UploadFile, File, Form
from typing import Optional, List
from uuid import UUID
import csv
import io

from src.api.backend.crud import TeamCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD, AnalysisJobCRUD
from src.api.backend.services.frontend_adapter import FrontendAdapter
from src.api.backend.background import run_analysis_job
from src.api.backend.utils.cache import cache, RedisCache

router = APIRouter(prefix="/api", tags=["frontend"])











@router.get("/leaderboard")
async def get_leaderboard(
    tech: Optional[str] = Query(None),
    sort: Optional[str] = Query(None, pattern="^(total|quality|security|originality|architecture|documentation)$"),
    search: Optional[str] = Query(None),
    # New parameters to support frontend format
    sort_by: Optional[str] = Query(None),
    order: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    batch_id: Optional[str] = Query(None)
):
    """
    Get leaderboard with filters (matches frontend LeaderboardEntry[])
    Note: Now queries teams table since projects table is dropped
    """ 
    try:
        from ..database import get_supabase_admin_client
        supabase = get_supabase_admin_client()

        # Handle both old and new parameter formats
        if sort_by:
            # Frontend format: sort_by=total_score, order=desc
            sort_field = sort_by
        elif sort:
            # Legacy format: sort=total
            sort_field = f"{sort}_score" if sort != "total" else "total_score"
        else:
            sort_field = "total_score"
        
        sort_order = order or "desc"
        
        # Check cache first (cache for 30 seconds)
        cache_key = f"hackeval:leaderboard:{tech}:{sort_field}:{sort_order}:{search}:{batch_id}:{page}:{page_size}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # OPTIMIZED: Single query with status filter, sorting, and tech stack join
        # Query teams table instead of projects
        query = supabase.table("teams").select(
            "id, team_name, repo_url, total_score, quality_score, security_score, "
            "originality_score, engineering_score, documentation_score, verdict, status"
        ).eq("status", "completed")
        
        # Apply batch filter if specified
        if batch_id:
            query = query.eq("batch_id", batch_id)
        
        # Apply search filter at database level
        if search:
            query = query.ilike("team_name", f"%{search}%")
        
        # Sort at database level
        query = query.order(sort_field, desc=(sort_order.lower() == "desc"))
        
        # Execute optimized query
        result = query.execute()
        teams = result.data or []
        
        # Early return if no teams
        if not teams:
            return {"leaderboard": [], "total": 0, "page": page, "page_size": page_size}
        
        # Get team IDs for tech stack fetch
        team_ids = [t["id"] for t in teams]
        
        # Single query for all tech stacks (using team_id)
        tech_response = supabase.table("tech_stack").select("team_id, technology").in_("team_id", team_ids).execute()
        tech_map = {}
        for tech_item in (tech_response.data or []):  # Use tech_item to avoid shadowing 'tech' query param
            tid = tech_item["team_id"]
            if tid not in tech_map:
                tech_map[tid] = []
            tech_map[tid].append(tech_item)
        
        # Transform using pre-fetched data
        results = []
        for team in teams:
            tid = team["id"]
            tech_stack = tech_map.get(tid, [])
            
            # Filter by tech if specified
            if tech:
                tech_names = [t.get("technology") for t in tech_stack]
                if tech not in tech_names:
                    continue
            
            item = FrontendAdapter.transform_leaderboard_item(team, tech_stack)
            results.append(item)

        # Add rank after filtering/sorting
        start_rank = (page - 1) * page_size
        for idx, item in enumerate(results):
            item["rank"] = start_rank + idx + 1
        
        # Return proper schema format
        response = {
            "leaderboard": results,
            "total": len(results),
            "page": page,
            "page_size": page_size
        }
        
        # Cache for 60 seconds (longer TTL for better perf)
        cache.set(cache_key, response, 60)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/leaderboard/chart")
async def get_leaderboard_chart():
    """
    Get leaderboard data for chart visualization
    Note: Now queries teams table since projects table is dropped
    """
    try:
        # Check cache
        cache_key = "hackeval:leaderboard:chart"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        from ..database import get_supabase_admin_client
        supabase = get_supabase_admin_client()
        
        # Query teams table for completed teams
        result = supabase.table("teams").select(
            "team_name, total_score, quality_score, security_score, originality_score, "
            "engineering_score, documentation_score"
        ).eq("status", "completed").order("total_score", desc=True).limit(10).execute()
        
        teams = result.data or []
        
        chart_data = []
        for team in teams:
            chart_data.append({
                "teamName": team.get("team_name"),
                "totalScore": team.get("total_score") or 0,
                "qualityScore": team.get("quality_score") or 0,
                "securityScore": team.get("security_score") or 0,
                "originalityScore": team.get("originality_score") or 0,
                "architectureScore": team.get("engineering_score") or 0,
                "documentationScore": team.get("documentation_score") or 0
            })
        
        # Cache for 1 minute
        cache.set(cache_key, chart_data, 60)
        
        return chart_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_dashboard_stats():
    """
    Get aggregate statistics for dashboard
    Note: Now queries teams table since projects table is dropped
    """
    try:
        # Check cache
        cache_key = "hackeval:stats"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        from ..database import get_supabase_admin_client
        supabase = get_supabase_admin_client()
        
        # Query teams table
        result = supabase.table("teams").select("id, status, total_score").execute()
        teams = result.data or []
        
        completed = [t for t in teams if t.get("status") == "completed"]
        in_progress = [t for t in teams if t.get("status") in ["pending", "processing", "analyzing"]]
        
        avg_score = 0
        if completed:
            total_scores = sum(t.get("total_score") or 0 for t in completed)
            avg_score = round(total_scores / len(completed), 1)
        
        # Get all tech stacks
        all_tech = set()
        if completed:
            team_ids = [t["id"] for t in completed]
            tech_result = supabase.table("tech_stack").select("technology").in_("team_id", team_ids).execute()
            for tech in (tech_result.data or []):
                tech_name = tech.get("technology")
                if tech_name:
                    all_tech.add(tech_name)
        
        # Count security issues
        total_issues = 0
        if completed:
            team_ids = [t["id"] for t in completed]
            issues_result = supabase.table("issues").select("type").in_("team_id", team_ids).execute()
            total_issues = len([i for i in (issues_result.data or []) if i.get("type") == "security"])
        
        result = {
            "totalProjects": len(teams),
            "completedProjects": len(completed),
            "pendingProjects": len(in_progress),  # Changed from inProgressProjects
            "averageScore": avg_score,  # Changed from avgScore
            "totalSecurityIssues": total_issues
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, result, RedisCache.TTL_MEDIUM)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/tech-stacks")
async def get_available_technologies():
    """
    Get list of all technologies used across projects
    Note: Now queries teams table since projects table is dropped
    """
    try:
        # Check cache
        cache_key = "hackeval:tech-stacks"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        from ..database import get_supabase_admin_client
        supabase = get_supabase_admin_client()
        
        # Get all teams
        teams_result = supabase.table("teams").select("id").execute()
        teams = teams_result.data or []
        
        tech_count = {}
        if teams:
            team_ids = [t["id"] for t in teams]
            tech_result = supabase.table("tech_stack").select("technology").in_("team_id", team_ids).execute()
            for tech in (tech_result.data or []):
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




@router.post("/batch-upload")
async def batch_upload(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Batch upload projects from CSV file - SEQUENTIAL PROCESSING
    Expected CSV columns: teamName, repoUrl, description (optional)
    
    Note: Now creates teams instead of projects since projects table is dropped
    
    Returns batchId for tracking progress via /api/batch/{batch_id}/status
    """
    from src.api.backend.crud import BatchCRUD, TeamCRUD
    from src.api.backend.background import run_batch_sequential
    
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
        
        # First pass: validate all rows and create teams/jobs
        repos_to_process = []
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
                # Check if team already exists with this repo URL
                existing = TeamCRUD.get_team_by_url(repo_url)
                if existing and existing.get("status") in ["analyzing", "completed"]:
                    failed_rows.append({
                        "row": row_num,
                        "teamName": team_name,
                        "repoUrl": repo_url,
                        "error": f"Already {existing.get('status')}"
                    })
                    continue
                
                # Create or update team
                if existing:
                    team_id = UUID(existing["id"])
                else:
                    # Create new team (simplified - no batch_id for now)
                    from ..database import get_supabase_admin_client
                    supabase = get_supabase_admin_client()
                    
                    team_data = {
                        "id": str(uuid4()),
                        "team_name": team_name,
                        "repo_url": repo_url,
                        "status": "pending"
                    }
                    
                    team_response = supabase.table("teams").insert(team_data).execute()
                    if not team_response.data:
                        raise Exception("Failed to create team")
                    
                    team_id = UUID(team_response.data[0]["id"])
                
                # Create job
                job = AnalysisJobCRUD.create_job(team_id)
                job_id = UUID(job["id"])
                
                # Add to processing queue
                repos_to_process.append({
                    "row": row_num,
                    "team_name": team_name,
                    "repo_url": repo_url,
                    "project_id": str(team_id),  # Keep as project_id for backward compatibility
                    "job_id": str(job_id)
                })
                
            except Exception as e:
                failed_rows.append({
                    "row": row_num,
                    "teamName": team_name,
                    "repoUrl": repo_url,
                    "error": str(e)
                })
        
        # Create batch record for tracking
        batch = None
        batch_id = None
        if repos_to_process:
            batch = BatchCRUD.create_batch(total_repos=len(repos_to_process))
            batch_id = batch["id"] if batch else None
            
            # Queue SINGLE background task for sequential processing
            if background_tasks and batch_id:
                background_tasks.add_task(
                    run_batch_sequential,
                    batch_id=batch_id,
                    repos=repos_to_process
                )
        
        # Build response for frontend
        queued_jobs = [
            {
                "row": r["row"],
                "teamName": r["team_name"],
                "repoUrl": r["repo_url"],
                "jobId": r["job_id"],
                "projectId": r["project_id"]  # Keep as projectId for backward compatibility
            }
            for r in repos_to_process
        ]
        
        return {
            "batchId": batch_id,  # NEW: for tracking
            "success": len(repos_to_process),
            "failed": len(failed_rows),
            "total": len(repos_to_process) + len(failed_rows),
            "queued": queued_jobs,
            "errors": failed_rows,
            "message": f"Successfully queued {len(repos_to_process)} teams for sequential processing, {len(failed_rows)} failed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"\n❌ BATCH UPLOAD ERROR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{batch_id}/status")
async def get_batch_status(batch_id: str):
    """
    Get the current status of a batch upload - for live progress tracking
    
    Returns:
        - status: pending/processing/completed/failed
        - total: total number of repos in batch
        - completed: number of completed repos
        - failed: number of failed repos
        - currentIndex: which repo is currently being analyzed (1-indexed)
        - currentRepo: URL of the repo being analyzed
        - currentTeam: team name of the repo being analyzed
    """
    from src.api.backend.crud import BatchCRUD
    
    try:
        batch = BatchCRUD.get_batch(batch_id)
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        return {
            "batchId": batch_id,
            "status": batch.get("status", "pending"),
            "total": batch.get("total_repos", 0),
            "completed": batch.get("completed_repos", 0),
            "failed": batch.get("failed_repos", 0),
            "currentIndex": batch.get("current_index", 0),
            "currentRepo": batch.get("current_repo_url"),
            "currentTeam": batch.get("current_repo_team"),
            "createdAt": batch.get("created_at"),
            "completedAt": batch.get("completed_at"),
            "errorMessage": batch.get("error_message")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

