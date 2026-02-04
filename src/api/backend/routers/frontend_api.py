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
        
        # Cache with status-appropriate TTL
        if project.get("status") == "completed":
            # Completed projects rarely change - cache for 5 minutes
            cache.set(cache_key, result, RedisCache.TTL_MEDIUM)
        elif project.get("status") in ["pending", "processing"]:
            # Processing projects change frequently - cache for 30 seconds to reduce rapid refreshes
            cache.set(cache_key, result, RedisCache.TTL_SHORT)
        elif project.get("status") == "failed":
            # Failed projects don't change - cache for 5 minutes
            cache.set(cache_key, result, RedisCache.TTL_MEDIUM)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/tree")
async def get_project_tree(project_id: str):
    """Get repository structure tree"""
    try:
        # Check cache first
        cache_key = f"hackeval:tree:{project_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Get project
        project = ProjectCRUD.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get tree from report_json
        report_json = project.get("report_json", {})
        print(f"[DEBUG] report_json keys: {list(report_json.keys())}")
        tree_text = report_json.get("repo_tree", "Repository structure not available")
        print(f"[DEBUG] repo_tree exists: {'repo_tree' in report_json}")
        print(f"[DEBUG] tree_text length: {len(tree_text) if tree_text else 0}")
        
        result = {
            "projectId": project_id,
            "tree": tree_text
        }
        
        # Cache for 1 hour (tree doesn't change)
        cache.set(cache_key, result, RedisCache.TTL_LONG)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/commits")
async def get_project_commits(project_id: str, author: Optional[str] = Query(None)):
    """Get detailed commit history with authors. If author is specified, return individual commits."""
    try:
        # Check cache first (skip cache for debugging)
        cache_key = f"hackeval:commits:{project_id}:{author or 'all'}"
        # cached_result = cache.get(cache_key)
        # if cached_result:
        #     return cached_result
        
        # Get project
        project = ProjectCRUD.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get commit details from report_json
        report_json = project.get("report_json", {})
        
        print(f"[DEBUG] report_json keys: {list(report_json.keys())}")
        
        # Try commit_details first (newer format), fall back to team field (older format)
        commit_details = report_json.get("commit_details", {})
        print(f"[DEBUG] commit_details keys: {list(commit_details.keys())}")
        
        author_stats = commit_details.get("author_stats", {})
        
        # Fallback: check if data is in "team" field (this is where agent.py stores it)
        if not author_stats:
            author_stats = report_json.get("team", {})
        
        # If author is specified, return their individual commits
        if author:
            all_commits = commit_details.get("all_commits", [])
            print(f"[DEBUG] Total commits in DB: {len(all_commits)}")
            print(f"[DEBUG] Filtering for author: {author}")
            author_commits = [c for c in all_commits if c["author"] == author]
            print(f"[DEBUG] Found {len(author_commits)} commits for {author}")
            # Sort by date descending (newest first)
            author_commits.sort(key=lambda x: x["date"], reverse=True)
            
            result = {
                "projectId": project_id,
                "author": author,
                "commits": author_commits
            }
        else:
            # Return aggregated stats for all authors
            print(f"[DEBUG] Project {project_id}: Found {len(author_stats)} authors")
            print(f"[DEBUG] Authors: {list(author_stats.keys())}")
            
            commits = []
            for author_name, stats in author_stats.items():
                commits.append({
                    "author": author_name,
                    "commits": stats.get("commits", 0),
                    "linesChanged": stats.get("lines_changed", 0),
                    "activeDays": stats.get("active_days_count", 0),
                    "topFileTypes": stats.get("top_file_types", "")
                })
            
            # Sort by commits descending
            commits.sort(key=lambda x: x["commits"], reverse=True)
            
            result = {
                "projectId": project_id,
                "totalCommits": commit_details.get("total_commits") or report_json.get("total_commits", 0),
                "authors": commits
            }
        
        # Cache for 1 hour
        cache.set(cache_key, result, RedisCache.TTL_LONG)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] Commits endpoint failed: {str(e)}")
        print(traceback.format_exc())
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
        
        # Batch fetch tech stacks and issues for all projects (fix N+1 query)
        from ..crud import get_supabase_client
        supabase = get_supabase_client()
        
        project_ids = [p["id"] for p in projects]
        if not project_ids:
            return []
        
        # Single query for all tech stacks
        tech_response = supabase.table("tech_stack").select("*").in_("project_id", project_ids).execute()
        tech_map = {}
        for tech in (tech_response.data or []):
            pid = tech["project_id"]
            if pid not in tech_map:
                tech_map[pid] = []
            tech_map[pid].append(tech)
        
        # Single query for all issues (only if needed for security count)
        issues_response = supabase.table("issues").select("project_id, type").in_("project_id", project_ids).execute()
        issues_map = {}
        for issue in (issues_response.data or []):
            pid = issue["project_id"]
            if pid not in issues_map:
                issues_map[pid] = []
            issues_map[pid].append(issue)
        
        # Transform each project using pre-fetched data
        results = []
        for project in projects:
            pid = project["id"]
            tech_stack = tech_map.get(pid, [])
            
            # Filter by tech if specified
            if tech:
                tech_names = [t.get("technology") for t in tech_stack]
                if tech not in tech_names:
                    continue
            
            # Count security issues from pre-fetched data
            issues = issues_map.get(pid, [])
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
        
        # Batch fetch tech stacks for all projects (fix N+1 query)
        from ..crud import get_supabase_client
        supabase = get_supabase_client()
        
        project_ids = [p["id"] for p in projects]
        if not project_ids:
            return {"leaderboard": [], "total": 0, "page": 1, "page_size": 0}
        
        # Single query for all tech stacks
        tech_response = supabase.table("tech_stack").select("*").in_("project_id", project_ids).execute()
        tech_map = {}
        for tech in (tech_response.data or []):
            pid = tech["project_id"]
            if pid not in tech_map:
                tech_map[pid] = []
            tech_map[pid].append(tech)
        
        # Transform using pre-fetched data
        results = []
        for project in projects:
            pid = project["id"]
            tech_stack = tech_map.get(pid, [])
            
            # Filter by tech if specified
            if tech:
                tech_names = [t.get("technology") for t in tech_stack]
                if tech not in tech_names:
                    continue
            
            item = FrontendAdapter.transform_leaderboard_item(project, tech_stack)
            results.append(item)
        
        # FIXED: Return proper schema format instead of raw array
        response = {
            "leaderboard": results,
            "total": len(results),
            "page": 1,
            "page_size": len(results)
        }
        
        # Cache for 30 seconds
        if not search:
            cache.set(cache_key, response, RedisCache.TTL_SHORT)
        
        return response
        
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
        
        # Cache for 5 minutes
        cache.set(cache_key, result, RedisCache.TTL_MEDIUM)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/clear-all")
async def clear_all_projects():
    """Delete all projects from database (dangerous operation)"""
    try:
        from ..crud import get_supabase_client
        supabase = get_supabase_client()
        
        # Get all projects
        projects, total = ProjectCRUD.list_projects()
        
        deleted_count = 0
        failed_count = 0
        
        for project in projects:
            try:
                project_id = project.get("id")
                
                # Delete related records first to avoid FK constraint violations
                # Delete tech_stack
                supabase.table("tech_stack").delete().eq("project_id", project_id).execute()
                
                # Delete team_members
                supabase.table("team_members").delete().eq("project_id", project_id).execute()
                
                # Delete analysis_jobs
                supabase.table("analysis_jobs").delete().eq("project_id", project_id).execute()
                
                # Delete project
                ProjectCRUD.delete_project(project_id)
                
                # Invalidate caches
                cache.delete(f"hackeval:project:{project_id}")
                cache.delete(f"hackeval:tree:{project_id}")
                cache.delete(f"hackeval:commits:{project_id}")
                
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete project {project_id}: {e}")
                failed_count += 1
        
        # Clear all list caches
        cache.delete("hackeval:projects:*")
        cache.delete("hackeval:leaderboard")
        cache.delete("hackeval:stats")
        cache.delete("hackeval:tech-stacks")
        
        return {
            "success": True,
            "deleted": deleted_count,
            "failed": failed_count,
            "message": f"Cleared {deleted_count} projects from database"
        }
        
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
        AnalysisJobCRUD.delete_by_project(project_id)
        
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
    Batch upload projects from CSV file - SEQUENTIAL PROCESSING
    Expected CSV columns: teamName, repoUrl, description (optional)
    
    Returns batchId for tracking progress via /api/batch/{batch_id}/status
    """
    from src.api.backend.crud import BatchCRUD
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
        
        # First pass: validate all rows and create projects/jobs
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
                
                # Add to processing queue
                repos_to_process.append({
                    "row": row_num,
                    "team_name": team_name,
                    "repo_url": repo_url,
                    "project_id": str(project_id),
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
                "projectId": r["project_id"]
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
            "message": f"Successfully queued {len(repos_to_process)} projects for sequential processing, {len(failed_rows)} failed"
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

