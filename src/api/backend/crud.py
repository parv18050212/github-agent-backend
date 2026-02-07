"""
CRUD Operations for Supabase Database
"""
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from src.api.backend.database import get_supabase_client, get_supabase_admin_client
from src.api.backend.utils.role_manager import RoleManager
from postgrest.exceptions import APIError


class ProjectCRUD:
    """CRUD operations for projects table"""
    
    @staticmethod
    def create_project(repo_url: str, team_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new project record"""
        supabase = get_supabase_client()
        
        try:
            # Generate UUID explicitly since DB doesn't have default
            project_id = str(uuid4())
            data = {
                "id": project_id,
                "repo_url": repo_url,
                "team_name": team_name,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            result = supabase.table("projects").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error creating project: {e}")
            raise
    
    @staticmethod
    def get_project(project_id: UUID) -> Optional[Dict[str, Any]]:
        """Get project by ID"""
        supabase = get_supabase_client()
        
        result = supabase.table("projects").select("*").eq("id", str(project_id)).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_project_by_url(repo_url: str) -> Optional[Dict[str, Any]]:
        """Get project by repository URL"""
        supabase = get_supabase_client()
        
        result = supabase.table("projects").select("*").eq("repo_url", repo_url).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_project(project_id: UUID, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update project fields"""
        supabase = get_supabase_client()
        
        try:
            result = supabase.table("projects").update(data).eq("id", str(project_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating project {project_id}: {e}")
            raise
    
    @staticmethod
    def update_project_status(project_id: UUID, status: str) -> Dict[str, Any]:
        """Update project status"""
        return ProjectCRUD.update_project(project_id, {"status": status})
    
    @staticmethod
    def update_project_scores(project_id: UUID, scores: Dict[str, float]) -> Dict[str, Any]:
        """Update project scores"""
        data = {
            **scores,
            "analyzed_at": datetime.now().isoformat(),
            "last_analyzed_at": datetime.now().isoformat()
        }
        return ProjectCRUD.update_project(project_id, data)
    
    @staticmethod
    def list_projects(
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        team_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Dict[str, Any]], int]:
        """List projects with filters and pagination"""
        supabase = get_supabase_admin_client()
        
        # Build query
        query = supabase.table("projects").select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        if min_score is not None:
            query = query.gte("total_score", min_score)
        if max_score is not None:
            query = query.lte("total_score", max_score)
        if team_name:
            query = query.ilike("team_name", f"%{team_name}%")
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size - 1
        query = query.range(start, end).order("created_at", desc=True)
        
        result = query.execute()
        total = result.count if hasattr(result, 'count') else len(result.data)
        
        return result.data, total
    
    @staticmethod
    def delete_project(project_id: UUID) -> bool:
        """Delete project (cascade deletes related records)"""
        supabase = get_supabase_client()
        
        result = supabase.table("projects").delete().eq("id", str(project_id)).execute()
        return len(result.data) > 0
    
    @staticmethod
    def get_leaderboard(
        sort_by: str = "total_score",
        order: str = "desc",
        page: int = 1,
        page_size: int = 20,
        status: str = "completed",
        batch_id: Optional[str] = None,
        mentor_id: Optional[str] = None
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get ranked projects leaderboard with optional batch and mentor filtering"""
        from src.api.backend.utils.cache import cache, RedisCache
        
        supabase = get_supabase_client()
        
        # Build count cache key
        count_cache_key = f"hackeval:leaderboard:count:{batch_id or 'all'}:{status}:{mentor_id or 'all'}"
        total = cache.get(count_cache_key)
        
        # Query without count for data (faster)
        query = supabase.table("projects").select("*")
        
        # Filter by batch or mentor if provided
        # Use teams.project_id to find projects (teams link TO projects, not vice versa)
        if batch_id or mentor_id:
            project_ids = set()
            
            # Base teams query
            teams_query = supabase.table("teams").select("project_id")
            if batch_id:
                teams_query = teams_query.eq("batch_id", batch_id)
            
            if mentor_id:
                # Use centralized logic for mentor team resolution
                mentor_team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
                # Need to map these team_ids to project_ids
                if mentor_team_ids:
                    t_res = supabase.table("teams").select("project_id").in_("id", mentor_team_ids).execute()
                    if t_res.data:
                        project_ids.update([t["project_id"] for t in t_res.data if t.get("project_id")])
            else:
                # Only batch_id filtering
                r = teams_query.execute()
                if r.data:
                    project_ids.update([t["project_id"] for t in r.data if t.get("project_id")])
            
            final_project_ids = list(project_ids)
            
            if not final_project_ids:
                return [], 0 # No matching teams
            
            query = query.in_("id", final_project_ids)
        
        # Filter by status
        query = query.eq("status", status)
        
        # Only include projects with scores
        query = query.not_.is_("total_score", "null")
        
        # Pagination
        start = (page - 1) * page_size
        end = start + page_size - 1
        
        # Sorting
        desc = (order.lower() == "desc")
        query = query.range(start, end).order(sort_by, desc=desc)
        
        result = query.execute()
        
        # If count not cached, run separate count query and cache it
        if total is None:
            count_query = supabase.table("projects").select("id", count="exact")
            
            # Apply same filters for count
            if batch_id or mentor_id:
                if final_project_ids:
                    count_query = count_query.in_("id", final_project_ids)
            count_query = count_query.eq("status", status)
            count_query = count_query.not_.is_("total_score", "null")
            
            count_result = count_query.execute()
            total = count_result.count if hasattr(count_result, 'count') else 0
            
            # Cache count for 30 seconds (balances freshness with performance)
            cache.set(count_cache_key, total, RedisCache.TTL_SHORT)
        
        # Add rank
        ranked_data = []
        for idx, item in enumerate(result.data):
            item['rank'] = start + idx + 1
            ranked_data.append(item)
        
        return ranked_data, total


class AnalysisJobCRUD:
    """CRUD operations for analysis_jobs table"""
    
    @staticmethod
    def create_job(project_id: UUID) -> Dict[str, Any]:
        """Create a new analysis job"""
        supabase = get_supabase_client()
        
        # Generate UUID explicitly since DB doesn't have default
        job_id = str(uuid4())
        data = {
            "id": job_id,
            "project_id": str(project_id),
            "status": "queued",
            "progress": 0,
            "started_at": datetime.now().isoformat()
        }
        
        result = supabase.table("analysis_jobs").insert(data).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_job(job_id: UUID) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        supabase = get_supabase_client()
        
        result = supabase.table("analysis_jobs").select("*").eq("id", str(job_id)).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_job_by_project(project_id: UUID) -> Optional[Dict[str, Any]]:
        """Get latest job for a project"""
        supabase = get_supabase_client()
        
        result = (supabase.table("analysis_jobs")
                 .select("*")
                 .eq("project_id", str(project_id))
                 .order("started_at", desc=True)
                 .limit(1)
                 .execute())
        
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_job_progress(job_id: UUID, progress: int, stage: Optional[str] = None) -> Dict[str, Any]:
        """Update job progress"""
        supabase = get_supabase_client()
        
        try:
            data = {
                "progress": progress,
                "status": "running"
            }
            
            if stage:
                data["current_stage"] = stage
            
            result = supabase.table("analysis_jobs").update(data).eq("id", str(job_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"Error updating job progress: {e}")
            # Don't raise - progress updates are non-critical
            return None
    
    @staticmethod
    def complete_job(job_id: UUID) -> Dict[str, Any]:
        """Mark job as completed"""
        supabase = get_supabase_client()
        
        data = {
            "status": "completed",
            "progress": 100,
            "completed_at": datetime.now().isoformat()
        }
        
        result = supabase.table("analysis_jobs").update(data).eq("id", str(job_id)).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def fail_job(job_id: UUID, error_message: str) -> Dict[str, Any]:
        """Mark job as failed"""
        supabase = get_supabase_client()
        
        data = {
            "status": "failed",
            "error_message": error_message,
            "completed_at": datetime.now().isoformat()
        }
        
        result = supabase.table("analysis_jobs").update(data).eq("id", str(job_id)).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def list_jobs(skip: int = 0, limit: int = 50, status: Optional[str] = None, latest_only: bool = True) -> tuple[List[Dict[str, Any]], int]:
        """
        List analysis status for projects (including pending ones).
        Queries PROJECTS table and joins latest analysis_job.
        """
        supabase = get_supabase_client()
        
        # 1. Query Projects
        # Select project fields + team name (via join) + latest job (via join?)
        # Supabase join: projects check tables... teams(name).
        # And analysis_jobs.
        
        # Note: 'latest_only' is effectively always True if we query projects as primary,
        # unless we want to show multiple jobs per project, which this view doesn't really support well if primary is project.
        # Given the requirement "show list of eligible teams", we generally want 1 row per team/project.
        
        query = (supabase.table("projects")
             .select("id, repo_url, team_name, status, created_at, analyzed_at, last_analyzed_at, analysis_jobs(*)", count="exact")
             .order("created_at", desc=True))
                 
        if status:
            if status == "pending":
                 # Match projects where status is pending
                 query = query.eq("status", "pending")
            else:
                 # Match projects where status matches
                 # Note: 'running' in stats might be 'analyzing' in project
                 if status == "running":
                     query = query.eq("status", "analyzing")
                 else:
                     query = query.eq("status", status)

        # Pagination
        query = query.range(skip, skip + limit - 1)
        
        result = query.execute()
        total = result.count if hasattr(result, 'count') else len(result.data)
        
        # Transform result to match frontend expectation
        # Frontend expects flat object with job details + team_name
        transformed_jobs = []
        
        for p in result.data:
            jobs = p.get("analysis_jobs", [])
            # Sort jobs by started_at (fallback to created_at) desc if multiple
            latest_job = None
            if jobs:
                jobs.sort(key=lambda x: x.get("started_at") or x.get("created_at") or "", reverse=True)
                latest_job = jobs[0]
            
            # Construct row
            if latest_job:
                last_analyzed_at = latest_job.get("completed_at")
            else:
                last_analyzed_at = p.get("last_analyzed_at") or p.get("analyzed_at")

            row = {
                "job_id": latest_job.get("id") if latest_job else None,
                "project_id": p.get("id"),
                "team_name": p.get("team_name") or "Unknown Team",
                "repo_url": p.get("repo_url"),
                "status": (latest_job.get("status") if latest_job else p.get("status")) or "pending", # Job status takes precedence if exists
                "progress": latest_job.get("progress", 0) if latest_job else 0,
                "current_stage": latest_job.get("current_stage") if latest_job else None,
                "started_at": latest_job.get("started_at") if latest_job else p.get("created_at"), # Use project create time if no job
                "completed_at": latest_job.get("completed_at") if latest_job else None,
                "last_analyzed_at": last_analyzed_at,
                "error_message": latest_job.get("error_message") if latest_job else None
            }
            transformed_jobs.append(row)
            
        return transformed_jobs, total

    @staticmethod
    def get_global_stats(latest_only: bool = True, batch_id: Optional[str] = None) -> Dict[str, int]:
        """
        Get global job statistics (counts by status)
        Only counts jobs for currently existing projects.
        
        Args:
            latest_only: If True, only count the latest job per project
            batch_id: Optional Batch UUID to filter by
        """
        supabase = get_supabase_client()
        
        try:
            # 1. Fetch ALL projects (filtered by batch if needed) to get the true source of truth
            query = supabase.table("projects").select("id, status")
            
            if batch_id:
                teams_result = supabase.table("teams").select("id").eq("batch_id", batch_id).execute()
                team_ids = [t["id"] for t in teams_result.data] if teams_result.data else []
                if not team_ids:
                     return {"queued": 0, "running": 0, "completed": 0, "failed": 0, "pending": 0}
                query = query.in_("team_id", team_ids)
                
            projects_result = query.execute()
            projects = projects_result.data
            
            stats = {"queued": 0, "running": 0, "completed": 0, "failed": 0, "pending": 0}
            
            # Count based on Project Status
            # We assume Project status is synced with Job status, or we default to 'pending'
            for p in projects:
                status = (p.get("status") or "pending").lower()
                
                # Normalize status
                if status == "analyzing":
                    stats["running"] += 1
                elif status in stats:
                    stats[status] += 1
                else:
                    # Treat unknown as pending or misc?
                    stats["pending"] += 1
            
            return stats
            
        except Exception as e:
            print(f"Error fetching global stats: {e}")
            return {"queued": 0, "running": 0, "completed": 0, "failed": 0}

    @staticmethod
    def delete_by_project(project_id: UUID) -> bool:
        """Delete all analysis jobs for a project"""
        supabase = get_supabase_client()
        result = supabase.table("analysis_jobs").delete().eq("project_id", str(project_id)).execute()
        return True


class TechStackCRUD:
    """CRUD operations for tech_stack table"""
    
    @staticmethod
    def add_technologies(project_id: UUID, technologies: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Add multiple technologies for a project (replaces existing tech stack)"""
        supabase = get_supabase_client()
        
        # Delete existing tech stack first to prevent duplicates on re-analysis
        supabase.table("tech_stack").delete().eq("project_id", str(project_id)).execute()
        
        if not technologies:
            return []
        
        # Deduplicate by technology name
        seen = set()
        unique_techs = []
        for tech in technologies:
            tech_name = tech.get("technology", "").strip().lower()
            if tech_name and tech_name not in seen:
                seen.add(tech_name)
                unique_techs.append(tech)
        
        if not unique_techs:
            return []
        
        data = [
            {
                "id": str(uuid4()),
                "project_id": str(project_id),
                "technology": tech.get("technology"),
                "category": tech.get("category")
            }
            for tech in unique_techs
        ]
        
        result = supabase.table("tech_stack").insert(data).execute()
        return result.data
    
    @staticmethod
    def get_tech_stack(project_id: UUID) -> List[Dict[str, Any]]:
        """Get all technologies for a project"""
        supabase = get_supabase_client()
        
        result = supabase.table("tech_stack").select("*").eq("project_id", str(project_id)).execute()
        return result.data
    
    @staticmethod
    def delete_by_project(project_id: UUID) -> bool:
        """Delete all technologies for a project"""
        supabase = get_supabase_client()
        result = supabase.table("tech_stack").delete().eq("project_id", str(project_id)).execute()
        return True


class IssueCRUD:
    """CRUD operations for issues table"""
    
    @staticmethod
    def add_issues(project_id: UUID, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add multiple issues for a project (replaces existing issues)"""
        supabase = get_supabase_client()
        
        # Delete existing issues first to prevent duplicates on re-analysis
        supabase.table("issues").delete().eq("project_id", str(project_id)).execute()
        
        if not issues:
            return []
        
        data = [
            {
                "id": str(uuid4()),
                "project_id": str(project_id),
                "type": issue.get("type"),
                "severity": issue.get("severity"),
                "file_path": issue.get("file_path"),
                "description": issue.get("description"),
                "ai_probability": issue.get("ai_probability"),
                "plagiarism_score": issue.get("plagiarism_score")
            }
            for issue in issues
        ]
        
        result = supabase.table("issues").insert(data).execute()
        return result.data
    
    @staticmethod
    def get_issues(project_id: UUID) -> List[Dict[str, Any]]:
        """Get all issues for a project"""
        supabase = get_supabase_client()
        
        result = supabase.table("issues").select("*").eq("project_id", str(project_id)).execute()
        return result.data
    
    @staticmethod
    def delete_by_project(project_id: UUID) -> bool:
        """Delete all issues for a project"""
        supabase = get_supabase_client()
        result = supabase.table("issues").delete().eq("project_id", str(project_id)).execute()
        return True


class TeamMemberCRUD:
    """CRUD operations for team_members table"""
    
    @staticmethod
    def add_members(project_id: UUID, members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add multiple team members for a project (replaces existing members)"""
        supabase = get_supabase_client()
        
        # Delete existing members first to prevent duplicates
        supabase.table("team_members").delete().eq("project_id", str(project_id)).execute()
        
        # Deduplicate members by name (prefer entry with more commits)
        members_by_name = {}
        for member in members:
            name = member.get("name", "").strip()
            if not name:
                continue
            existing = members_by_name.get(name)
            if not existing or (member.get("commits", 0) or 0) > (existing.get("commits", 0) or 0):
                members_by_name[name] = member
        
        if not members_by_name:
            return []
        
        data = [
            {
                "id": str(uuid4()),
                "project_id": str(project_id),
                "name": member.get("name"),
                "commits": member.get("commits"),
                "contribution_pct": member.get("contribution_pct")
            }
            for member in members_by_name.values()
        ]
        
        result = supabase.table("team_members").insert(data).execute()
        return result.data
    
    @staticmethod
    def get_team_members(project_id: UUID) -> List[Dict[str, Any]]:
        """Get all team members for a project"""
        supabase = get_supabase_client()
        
        result = supabase.table("team_members").select("*").eq("project_id", str(project_id)).execute()
        return result.data
    
    @staticmethod
    def delete_by_project(project_id: UUID) -> bool:
        """Delete all team members for a project"""
        supabase = get_supabase_client()
        result = supabase.table("team_members").delete().eq("project_id", str(project_id)).execute()
        return True


class BatchCRUD:
    """CRUD operations for batches table (sequential batch processing)"""
    
    @staticmethod
    def create_batch(total_repos: int) -> Dict[str, Any]:
        """Create a new batch record"""
        supabase = get_supabase_client()
        
        batch_id = str(uuid4())
        data = {
            "id": batch_id,
            "status": "pending",
            "total_repos": total_repos,
            "completed_repos": 0,
            "failed_repos": 0,
            "current_index": 0,
            "created_at": datetime.now().isoformat()
        }
        
        result = supabase.table("batches").insert(data).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
        """Get batch by ID"""
        supabase = get_supabase_client()
        
        result = supabase.table("batches").select("*").eq("id", batch_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def update_batch_progress(
        batch_id: str, 
        current_index: int, 
        current_repo_url: str, 
        current_repo_team: str
    ) -> Dict[str, Any]:
        """Update batch progress with current repo being analyzed"""
        supabase = get_supabase_client()
        
        data = {
            "status": "processing",
            "current_index": current_index,
            "current_repo_url": current_repo_url,
            "current_repo_team": current_repo_team
        }
        
        result = supabase.table("batches").update(data).eq("id", batch_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def increment_completed(batch_id: str) -> Dict[str, Any]:
        """Increment completed count for batch"""
        supabase = get_supabase_client()
        
        # Get current count
        batch = BatchCRUD.get_batch(batch_id)
        if not batch:
            return None
        
        new_count = (batch.get("completed_repos") or 0) + 1
        result = supabase.table("batches").update({"completed_repos": new_count}).eq("id", batch_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def increment_failed(batch_id: str) -> Dict[str, Any]:
        """Increment failed count for batch"""
        supabase = get_supabase_client()
        
        # Get current count
        batch = BatchCRUD.get_batch(batch_id)
        if not batch:
            return None
        
        new_count = (batch.get("failed_repos") or 0) + 1
        result = supabase.table("batches").update({"failed_repos": new_count}).eq("id", batch_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def complete_batch(batch_id: str) -> Dict[str, Any]:
        """Mark batch as completed"""
        supabase = get_supabase_client()
        
        data = {
            "status": "completed",
            "current_repo_url": None,
            "current_repo_team": None,
            "completed_at": datetime.now().isoformat()
        }
        
        result = supabase.table("batches").update(data).eq("id", batch_id).execute()
        return result.data[0] if result.data else None
    
    @staticmethod
    def fail_batch(batch_id: str, error_message: str) -> Dict[str, Any]:
        """Mark batch as failed"""
        supabase = get_supabase_client()
        
        data = {
            "status": "failed",
            "error_message": error_message,
            "completed_at": datetime.now().isoformat()
        }
        
        result = supabase.table("batches").update(data).eq("id", batch_id).execute()
        return result.data[0] if result.data else None


class UserCRUD:
    """CRUD operations for public.users profile table"""

    @staticmethod
    def get_user(user_id: str) -> Optional[Dict[str, Any]]:
        # Use admin client to bypass RLS policies
        supabase = get_supabase_admin_client()
        result = supabase.table("users").select("*").eq("id", user_id).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_or_create_user(user_id: str, email: Optional[str] = None, full_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get or create user with intelligent role assignment.
        
        Role determination priority:
        1. Supabase Auth metadata (app_metadata or user_metadata)
        2. First user in system becomes admin
        3. Admin email whitelist (ADMIN_EMAILS env var)
        4. Default to 'mentor'
        
        Note: Domain-based auto-admin removed to prevent accidentally making
        all college/university users admins when mentors also use those domains.
        """
        # Use admin client to bypass RLS policies
        supabase = get_supabase_admin_client()

        existing = UserCRUD.get_user(user_id)
        if existing:
            if full_name and not existing.get("full_name"):
                try:
                    supabase.table("users").update({"full_name": full_name}).eq("id", user_id).execute()
                    existing["full_name"] = full_name
                except Exception as e:
                    print(f"[UserCRUD] Failed to update full_name for {user_id}: {e}")
            return existing

        # Check if this is the first user in the system
        is_first_user = False
        try:
            user_count_response = supabase.table("users").select("id", count="exact").execute()
            user_count = user_count_response.count if hasattr(user_count_response, 'count') else len(user_count_response.data or [])
            is_first_user = (user_count == 0)
            if is_first_user:
                print(f"[UserCRUD] First user detected! Will assign admin role.")
        except Exception as e:
            print(f"[UserCRUD] Could not check user count: {e}")

        # Fetch auth metadata from Supabase Auth
        auth_metadata = {}
        try:
            user_response = supabase.auth.admin.get_user_by_id(user_id)
            if user_response and user_response.user:
                # Combine app_metadata and user_metadata
                app_metadata = user_response.user.app_metadata or {}
                user_metadata = user_response.user.user_metadata or {}
                
                # Priority: app_metadata.role > user_metadata.role
                if "role" in app_metadata:
                    auth_metadata["role"] = app_metadata["role"]
                elif "role" in user_metadata:
                    auth_metadata["role"] = user_metadata["role"]
                
                print(f"[UserCRUD] Auth metadata fetched: {auth_metadata}")
        except Exception as e:
            print(f"[UserCRUD] Could not fetch auth metadata: {e}")

        # Use RoleManager to intelligently determine role
        assigned_role = RoleManager.determine_role(
            email=email,
            auth_metadata=auth_metadata,
            is_first_user=is_first_user
        )

        payload = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "role": assigned_role,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }

        print(f"[UserCRUD] Creating user {email} with role: {assigned_role}")
        result = supabase.table("users").insert(payload).execute()
        return result.data[0] if result.data else payload

    @staticmethod
    def set_role(user_id: str, role: str) -> Dict[str, Any]:
        # Use admin client to bypass RLS policies
        supabase = get_supabase_admin_client()
        result = supabase.table("users").update({"role": role}).eq("id", user_id).execute()
        return result.data[0] if result.data else None


class MentorCRUD:
    """CRUD operations for mentors"""

    @staticmethod
    def create_mentor(user_id: str, expertise_areas: Optional[list] = None, max_teams: int = 5, bio: Optional[str] = None) -> Dict[str, Any]:
        supabase = get_supabase_client()
        data = {
            "user_id": user_id,
            "expertise_areas": expertise_areas or [],
            "max_teams": max_teams,
            "bio": bio,
            "created_at": datetime.now().isoformat()
        }
        result = supabase.table("mentors").insert(data).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def get_by_user(user_id: str) -> Optional[Dict[str, Any]]:
        supabase = get_supabase_client()
        result = supabase.table("mentors").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None


class TeamCRUD:
    """CRUD operations for teams and memberships"""

    @staticmethod
    def create_team(name: str, mentor_id: Optional[str] = None, description: Optional[str] = None, is_active: bool = True) -> Dict[str, Any]:
        supabase = get_supabase_client()
        data = {
            "name": name,
            "mentor_id": mentor_id,
            "description": description,
            "is_active": is_active,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        result = supabase.table("teams").insert(data).execute()
        return result.data[0] if result.data else None

    @staticmethod
    def list_teams() -> List[Dict[str, Any]]:
        supabase = get_supabase_client()
        result = supabase.table("teams").select("*").order("created_at", desc=True).execute()
        return result.data or []

    @staticmethod
    def add_member(team_id: str, user_id: str, role: str = "member") -> Dict[str, Any]:
        supabase = get_supabase_client()
        data = {
            "team_id": team_id,
            "user_id": user_id,
            "role": role,
            "joined_at": datetime.now().isoformat()
        }
        result = supabase.table("team_memberships").upsert(data, on_conflict="team_id,user_id").execute()
        return result.data[0] if result.data else data

    @staticmethod
    def list_members(team_id: str) -> List[Dict[str, Any]]:
        supabase = get_supabase_client()
        result = supabase.table("team_memberships").select("*").eq("team_id", team_id).execute()
        return result.data or []

    @staticmethod
    def get_mentor_team_ids(mentor_id: str) -> List[str]:
        """
        Get all team IDs assigned to a mentor using hybrid strategy.
        Checks both 'teams.mentor_id' (legacy) and 'mentor_team_assignments' (new).
        """
        from src.api.backend.utils.cache import cache, RedisCache

        cache_key = f"hackeval:mentor:team_ids:{mentor_id}"
        cached_ids = cache.get(cache_key)
        if cached_ids:
            return cached_ids

        supabase = get_supabase_client()
        team_ids = set()
        
        # A. Check 'teams' table direct column
        try:
            t_direct = supabase.table("teams").select("id").eq("mentor_id", mentor_id).execute()
            if t_direct.data:
                team_ids.update([t["id"] for t in t_direct.data])
        except Exception as e:
            print(f"[TeamCRUD] Warning fetching direct mentor teams: {e}")

        # B. Check 'mentor_team_assignments' junction table
        try:
            assignments = supabase.table("mentor_team_assignments").select("team_id").eq("mentor_id", str(mentor_id)).execute()
            if assignments.data:
                team_ids.update([a["team_id"] for a in assignments.data])
        except Exception as e:
            print(f"[TeamCRUD] Warning fetching mentor assignments: {e}")
            
        team_id_list = list(team_ids)
        cache.set(cache_key, team_id_list, RedisCache.TTL_SHORT)
        return team_id_list


class ProjectCommentCRUD:
    """CRUD operations for project_comments"""

    @staticmethod
    def add_comment(project_id: str, user_id: str, comment: str, is_private: bool = False) -> Dict[str, Any]:
        supabase = get_supabase_client()
        data = {
            "project_id": project_id,
            "user_id": user_id,
            "comment": comment,
            "is_private": is_private,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        result = supabase.table("project_comments").insert(data).execute()
        return result.data[0] if result.data else data

    @staticmethod
    def list_comments(project_id: str) -> List[Dict[str, Any]]:
        supabase = get_supabase_client()
        result = supabase.table("project_comments").select("*").eq("project_id", project_id).order("created_at", desc=True).execute()
        return result.data or []

    @staticmethod
    def delete_comment(comment_id: str, requesting_user: str, is_admin: bool) -> bool:
        supabase = get_supabase_client()
        query = supabase.table("project_comments").delete().eq("id", comment_id)
        if not is_admin:
            query = query.eq("user_id", requesting_user)
        result = query.execute()
        return bool(result.data)
