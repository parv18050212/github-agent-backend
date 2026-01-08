"""
CRUD Operations for Supabase Database
"""
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from backend.database import get_supabase_client
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
            "analyzed_at": datetime.now().isoformat()
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
        supabase = get_supabase_client()
        
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
        status: str = "completed"
    ) -> tuple[List[Dict[str, Any]], int]:
        """Get ranked projects leaderboard"""
        supabase = get_supabase_client()
        
        query = supabase.table("projects").select("*", count="exact")
        
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
        total = result.count if hasattr(result, 'count') else len(result.data)
        
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


class TechStackCRUD:
    """CRUD operations for tech_stack table"""
    
    @staticmethod
    def add_technologies(project_id: UUID, technologies: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Add multiple technologies for a project"""
        supabase = get_supabase_client()
        
        data = [
            {
                "id": str(uuid4()),
                "project_id": str(project_id),
                "technology": tech.get("technology"),
                "category": tech.get("category")
            }
            for tech in technologies
        ]
        
        result = supabase.table("tech_stack").insert(data).execute()
        return result.data
    
    @staticmethod
    def get_tech_stack(project_id: UUID) -> List[Dict[str, Any]]:
        """Get all technologies for a project"""
        supabase = get_supabase_client()
        
        result = supabase.table("tech_stack").select("*").eq("project_id", str(project_id)).execute()
        return result.data


class IssueCRUD:
    """CRUD operations for issues table"""
    
    @staticmethod
    def add_issues(project_id: UUID, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add multiple issues for a project"""
        supabase = get_supabase_client()
        
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


class TeamMemberCRUD:
    """CRUD operations for team_members table"""
    
    @staticmethod
    def add_members(project_id: UUID, members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add multiple team members for a project"""
        supabase = get_supabase_client()
        
        data = [
            {
                "id": str(uuid4()),
                "project_id": str(project_id),
                "name": member.get("name"),
                "commits": member.get("commits"),
                "contribution_pct": member.get("contribution_pct")
            }
            for member in members
        ]
        
        result = supabase.table("team_members").insert(data).execute()
        return result.data
    
    @staticmethod
    def get_team_members(project_id: UUID) -> List[Dict[str, Any]]:
        """Get all team members for a project"""
        supabase = get_supabase_client()
        
        result = supabase.table("team_members").select("*").eq("project_id", str(project_id)).execute()
        return result.data
