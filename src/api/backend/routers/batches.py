"""
Batch Management Router
Handles CRUD operations for academic batches/semesters
"""
from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from ..schemas import (
    BatchCreateRequest,
    BatchUpdateRequest,
    BatchResponse,
    BatchStatsResponse,
    BatchListResponse,
    ErrorResponse
)
from ..middleware import get_current_user, AuthUser, RoleChecker
from ..database import get_supabase_admin_client

router = APIRouter(prefix="/api/batches", tags=["Batch Management"])


@router.post(
    "",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["admin"]))]
)
async def create_batch(
    batch_data: BatchCreateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Create a new batch (Admin only)
    
    **Required fields:**
    - name: Batch name (e.g., "4th Sem 2024")
    - semester: Semester (e.g., "4th Sem", "6th Sem")
    - year: Year (e.g., 2024)
    - start_date: Batch start date
    - end_date: Batch end date
    
    **Permissions:** Admin only
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Check if batch already exists
        existing = supabase.table("batches")\
            .select("id")\
            .eq("semester", batch_data.semester)\
            .eq("year", batch_data.year)\
            .execute()
        
        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch {batch_data.semester} {batch_data.year} already exists"
            )
        
        # Create batch
        batch = {
            "name": batch_data.name,
            "program": batch_data.program,
            "semester": batch_data.semester,
            "year": batch_data.year,
            "start_date": batch_data.start_date.isoformat(),
            "end_date": batch_data.end_date.isoformat(),
            "status": "active"
        }
        
        result = supabase.table("batches").insert(batch).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create batch"
            )
        
        created_batch = result.data[0]
        
        return BatchResponse(
            id=UUID(created_batch["id"]),
            name=created_batch["name"],
            program=created_batch.get("program"),
            semester=created_batch["semester"],
            year=created_batch["year"],
            start_date=datetime.fromisoformat(created_batch["start_date"].replace("Z", "+00:00")),
            end_date=datetime.fromisoformat(created_batch["end_date"].replace("Z", "+00:00")),
            status=created_batch["status"],
            team_count=created_batch.get("team_count", 0),
            student_count=created_batch.get("student_count", 0),
            created_at=datetime.fromisoformat(created_batch["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(created_batch["updated_at"].replace("Z", "+00:00"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create batch: {str(e)}"
        )


@router.get("", response_model=BatchListResponse)
async def list_batches(
    status_filter: Optional[str] = Query(None, description="Filter by status: active, archived, upcoming"),
    year: Optional[int] = Query(None, description="Filter by year"),
    current_user: Optional[AuthUser] = Depends(get_current_user)
):
    """
    List all batches
    
    **Query parameters:**
    - status: Filter by status (active, archived, upcoming)
    - year: Filter by year
    
    **Permissions:** Authenticated users (mentors and admins)
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Build query
        query = supabase.table("batches").select("*")
        
        if status_filter:
            query = query.eq("status", status_filter)
        
        if year:
            query = query.eq("year", year)
        
        # Order by year desc, then semester
        query = query.order("year", desc=True).order("semester", desc=False)
        
        result = query.execute()
        
        batches = []
        for batch in result.data:
            batches.append(BatchResponse(
                id=UUID(batch["id"]),
                name=batch["name"],
                program=batch.get("program"),
                semester=batch["semester"],
                year=batch["year"],
                start_date=datetime.fromisoformat(batch["start_date"].replace("Z", "+00:00")),
                end_date=datetime.fromisoformat(batch["end_date"].replace("Z", "+00:00")),
                status=batch["status"],
                team_count=batch.get("team_count", 0),
                student_count=batch.get("student_count", 0),
                created_at=datetime.fromisoformat(batch["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(batch["updated_at"].replace("Z", "+00:00"))
            ))
        
        return BatchListResponse(
            batches=batches,
            total=len(batches)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch batches: {str(e)}"
        )


@router.get("/{batch_id}", response_model=BatchStatsResponse)
async def get_batch(
    batch_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get batch by ID with statistics
    
    **Returns:**
    - Basic batch info
    - Team and student counts
    - Average score
    - Project completion stats
    - At-risk team count
    
    **Permissions:** Authenticated users
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Get batch
        batch_result = supabase.table("batches")\
            .select("*")\
            .eq("id", str(batch_id))\
            .execute()
        
        if not batch_result.data or len(batch_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        batch = batch_result.data[0]
        
        # Get teams in this batch
        teams_result = supabase.table("teams")\
            .select("id, project_id, health_status")\
            .eq("batch_id", str(batch_id))\
            .execute()
        
        teams = teams_result.data or []
        
        # Calculate statistics
        at_risk_teams = sum(1 for t in teams if t.get("health_status") in ["at_risk", "critical"])
        
        # Get project IDs for score calculation
        project_ids = [t["project_id"] for t in teams if t.get("project_id")]
        
        avg_score = None
        completed_projects = 0
        pending_projects = 0
        
        if project_ids:
            # Get teams (projects table has been dropped and merged into teams)
            teams_result = supabase.table("teams")\
                .select("id, status, total_score")\
                .in_("id", [str(pid) for pid in project_ids])\
                .execute()
            
            teams = teams_result.data or []
            
            completed_projects = sum(1 for t in teams if t.get("status") == "completed")
            pending_projects = sum(1 for t in teams if t.get("status") in ["pending", "analyzing"])
            
            # Calculate average score for completed teams
            scores = [t["total_score"] for t in teams if t.get("total_score") is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
        
        return BatchStatsResponse(
            id=UUID(batch["id"]),
            name=batch["name"],
            program=batch.get("program"),
            semester=batch["semester"],
            year=batch["year"],
            start_date=datetime.fromisoformat(batch["start_date"].replace("Z", "+00:00")),
            end_date=datetime.fromisoformat(batch["end_date"].replace("Z", "+00:00")),
            status=batch["status"],
            team_count=batch.get("team_count", 0),
            student_count=batch.get("student_count", 0),
            avg_score=avg_score,
            completed_projects=completed_projects,
            pending_projects=pending_projects,
            at_risk_teams=at_risk_teams,
            created_at=datetime.fromisoformat(batch["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(batch["updated_at"].replace("Z", "+00:00"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch batch: {str(e)}"
        )


@router.put(
    "/{batch_id}",
    response_model=BatchResponse,
    dependencies=[Depends(RoleChecker(["admin"]))]
)
async def update_batch(
    batch_id: UUID,
    batch_data: BatchUpdateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Update batch (Admin only)
    
    **Updatable fields:**
    - name
    - semester
    - year
    - start_date
    - end_date
    - status
    
    **Permissions:** Admin only
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Check if batch exists
        existing = supabase.table("batches")\
            .select("id")\
            .eq("id", str(batch_id))\
            .execute()
        
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        # Prepare update data
        update_data = {}
        if batch_data.name is not None:
            update_data["name"] = batch_data.name
        if batch_data.program is not None:
            update_data["program"] = batch_data.program
        if batch_data.semester is not None:
            update_data["semester"] = batch_data.semester
        if batch_data.year is not None:
            update_data["year"] = batch_data.year
        if batch_data.start_date is not None:
            update_data["start_date"] = batch_data.start_date.isoformat()
        if batch_data.end_date is not None:
            update_data["end_date"] = batch_data.end_date.isoformat()
        if batch_data.status is not None:
            update_data["status"] = batch_data.status
        
        if not update_data:
            # No updates provided, return current batch
            result = supabase.table("batches")\
                .select("*")\
                .eq("id", str(batch_id))\
                .execute()
            updated_batch = result.data[0]
        else:
            # Update batch
            result = supabase.table("batches")\
                .update(update_data)\
                .eq("id", str(batch_id))\
                .execute()
            
            if not result.data or len(result.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to update batch"
                )
            
            updated_batch = result.data[0]
        
        return BatchResponse(
            id=UUID(updated_batch["id"]),
            name=updated_batch["name"],
            program=updated_batch.get("program"),
            semester=updated_batch["semester"],
            year=updated_batch["year"],
            start_date=datetime.fromisoformat(updated_batch["start_date"].replace("Z", "+00:00")),
            end_date=datetime.fromisoformat(updated_batch["end_date"].replace("Z", "+00:00")),
            status=updated_batch["status"],
            team_count=updated_batch.get("team_count", 0),
            student_count=updated_batch.get("student_count", 0),
            created_at=datetime.fromisoformat(updated_batch["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(updated_batch["updated_at"].replace("Z", "+00:00"))
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update batch: {str(e)}"
        )


@router.post(
    "/{batch_id}/analyze",
    dependencies=[Depends(RoleChecker(["admin"]))]
)
async def trigger_batch_analysis(
    batch_id: UUID,
    force: bool = Query(False, description="Force re-analysis of all teams, ignoring the 7-day interval"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Trigger weekly analysis for all teams in a batch (Admin only)
    
    Creates a new batch_analysis_run and queues analysis jobs for teams using Celery.
    
    By default, only teams that haven't been analyzed within the last 7 days will be
    included. Use force=true to re-analyze all teams regardless of when they were last analyzed.
    
    **Permissions:** Admin only
    """
    try:
        # Import Celery task
        try:
            from celery_worker import process_batch_sequential
            CELERY_ENABLED = True
        except ImportError:
            CELERY_ENABLED = False
        
        supabase = get_supabase_admin_client()
        
        # Check if batch exists
        batch_result = supabase.table("batches")\
            .select("id, start_date")\
            .eq("id", str(batch_id))\
            .execute()
        
        if not batch_result.data or len(batch_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        # Calculate current week number
        batch = batch_result.data[0]
        
        # Get all teams in this batch (projects table has been dropped)
        teams_result = supabase.table("teams")\
            .select("id, team_name, repo_url, status")\
            .eq("batch_id", str(batch_id))\
            .execute()
        
        teams = teams_result.data or []
        total_teams = len(teams)
        
        if total_teams == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No teams found in this batch"
            )
        
        # Get current run number (last run + 1)
        last_run_result = supabase.table("batch_analysis_runs")\
            .select("run_number")\
            .eq("batch_id", str(batch_id))\
            .order("run_number", desc=True)\
            .limit(1)\
            .execute()
        
        run_number = 1
        if last_run_result.data and len(last_run_result.data) > 0:
            run_number = last_run_result.data[0]["run_number"] + 1
        
        # Create batch analysis run
        run_insert = {
            "batch_id": str(batch_id),
            "run_number": run_number,
            "status": "pending",
            "total_teams": total_teams,
            "completed_teams": 0,
            "failed_teams": 0
        }
        
        run_result = supabase.table("batch_analysis_runs")\
            .insert(run_insert)\
            .execute()
        
        if not run_result.data or len(run_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create batch analysis run"
            )
        
        run_id = run_result.data[0]["id"]
        
        # Build repos list for batch processing
        repos = []
        jobs_created = 0
        jobs_skipped = 0
        skipped_reasons = []
        
        # Import re-analysis check
        from src.api.backend.routers.analysis import should_allow_reanalysis
        
        for team in teams:
            # Projects table has been dropped - all data is now in teams table
            team_id = team["id"]
            repo_url = team.get("repo_url")
            
            if not repo_url:
                jobs_skipped += 1
                skipped_reasons.append(f"{team['team_name']}: No repository URL")
                continue
            
            # Check if re-analysis should be allowed (auto-scheduled analysis respects interval)
            # Pass team data directly (team is now the project)
            allowed, reason = should_allow_reanalysis(team, force=force)
            if not allowed:
                jobs_skipped += 1
                skipped_reasons.append(f"{team['team_name']}: {reason}")
                continue
            
            # Create analysis job
            job_insert = {
                "team_id": team_id,  # Changed from project_id to team_id
                "status": "queued",
                "requested_by": str(current_user.user_id),
                "started_at": datetime.now().isoformat(),
                "metadata": {
                    "batch_run_id": run_id,
                    "run_number": run_number,
                    "team_id": team_id
                }
            }
            
            try:
                job_result = supabase.table("analysis_jobs").insert(job_insert).execute()
                job_id = job_result.data[0]["id"]
                
                # Update team status (projects table has been dropped)
                supabase.table("teams").update({
                    "status": "queued"
                }).eq("id", team_id).execute()
                
                repos.append({
                    "project_id": team_id,  # Using team_id (kept as project_id for Celery compatibility)
                    "job_id": job_id,
                    "repo_url": repo_url,
                    "team_name": team["team_name"]
                })
                jobs_created += 1
            except Exception as e:
                print(f"Failed to create job for team {team['team_name']}: {e}")
                jobs_skipped += 1
                skipped_reasons.append(f"{team['team_name']}: {str(e)}")
        
        # Queue Celery batch task (or fallback to sequential processing)
        celery_queued = False
        if CELERY_ENABLED and repos:
            try:
                task = process_batch_sequential.delay(str(batch_id), repos)
                # Store Celery task ID
                supabase.table("batch_analysis_runs").update({
                    "status": "running",
                    "started_at": datetime.now().isoformat(),
                    "metadata": {"celery_task_id": task.id}
                }).eq("id", run_id).execute()
                celery_queued = True
                print(f"✓ Batch analysis queued via Celery (task_id: {task.id})")
            except Exception as celery_error:
                print(f"⚠ Celery queueing failed: {celery_error}")
                print("  Falling back to in-process background tasks...")
        
        # Fallback: Use old background task method
        if not celery_queued:
            supabase.table("batch_analysis_runs").update({
                "status": "running",
                "started_at": datetime.now().isoformat()
            }).eq("id", run_id).execute()
            
            # Check if background module exists
            try:
                from src.api.backend.background import run_batch_sequential
                import asyncio
                asyncio.create_task(run_batch_sequential(str(batch_id), repos))
                print(f"✓ Batch analysis queued via background tasks")
            except ImportError:
                print("⚠ Background task module not found - jobs created but not processing")
        
        return {
            "run_id": run_id,
            "run_number": run_number,
            "status": "running" if jobs_created > 0 else "skipped",
            "total_teams": total_teams,
            "jobs_created": jobs_created,
            "jobs_skipped": jobs_skipped,
            "skipped_reasons": skipped_reasons[:10] if skipped_reasons else [],  # Limit to first 10
            "message": f"Batch analysis run {run_number}: {jobs_created} teams queued, {jobs_skipped} skipped (already analyzed within interval)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger batch analysis: {str(e)}"
        )


@router.get(
    "/{batch_id}/runs"
)
async def get_batch_analysis_runs(
    batch_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get all analysis runs for a batch
    
    Returns list of weekly analysis runs with statistics.
    
    **Permissions:** Authenticated users
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Check if batch exists
        batch_result = supabase.table("batches")\
            .select("id")\
            .eq("id", str(batch_id))\
            .execute()
        
        if not batch_result.data or len(batch_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        # Get all runs for this batch
        runs_result = supabase.table("batch_analysis_runs")\
            .select("*")\
            .eq("batch_id", str(batch_id))\
            .order("run_number", desc=True)\
            .execute()
        
        runs = runs_result.data or []
        
        return {
            "batch_id": str(batch_id),
            "runs": runs,
            "total_runs": len(runs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch batch runs: {str(e)}"
        )


@router.get(
    "/{batch_id}/progress"
)
async def get_batch_progress(
    batch_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get current analysis run progress for a batch
    
    Returns status of the most recent analysis run (for UI polling).
    
    **Permissions:** Authenticated users
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Check if batch exists
        batch_result = supabase.table("batches")\
            .select("id, name")\
            .eq("id", str(batch_id))\
            .execute()
        
        if not batch_result.data or len(batch_result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        # Get most recent run
        runs_result = supabase.table("batch_analysis_runs")\
            .select("*")\
            .eq("batch_id", str(batch_id))\
            .order("run_number", desc=True)\
            .limit(1)\
            .execute()
        
        if not runs_result.data or len(runs_result.data) == 0:
            # No runs yet
            return {
                "status": "pending",
                "processed_teams": 0,
                "total_teams": 0,
                "current_team": None,
                "start_time": None,
                "end_time": None,
                "successful_analyses": 0,
                "failed_analyses": 0
            }
        
        latest_run = runs_result.data[0]
        
        # Determine status based on run data
        status_map = {
            "pending": "pending",
            "running": "in_progress",
            "completed": "completed",
            "failed": "failed"
        }
        
        status = status_map.get(latest_run["status"], "pending")
        
        # Get current job being processed (if any)
        current_team_name = None
        if status == "in_progress":
            current_job = supabase.table("analysis_jobs")\
                .select("teams(team_name)")\
                .eq("status", "processing")\
                .eq("batch_id", str(batch_id))\
                .limit(1)\
                .execute()
            
            if current_job.data and len(current_job.data) > 0:
                teams_data = current_job.data[0].get("teams")
                if teams_data:
                    current_team_name = teams_data.get("team_name") if isinstance(teams_data, dict) else None
        
        return {
            "status": status,
            "processed_teams": latest_run["completed_teams"] + latest_run["failed_teams"],
            "total_teams": latest_run["total_teams"],
            "current_team": current_team_name,
            "start_time": latest_run.get("started_at"),
            "end_time": latest_run.get("completed_at"),
            "successful_analyses": latest_run["completed_teams"],
            "failed_analyses": latest_run["failed_teams"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch batch progress: {str(e)}"
        )


@router.delete(
    "/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RoleChecker(["admin"]))]
)
async def delete_batch(
    batch_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Delete batch (Admin only)
    
    **Warning:** This will cascade delete all teams and students in the batch
    
    **Permissions:** Admin only
    """
    try:
        supabase = get_supabase_admin_client()
        
        # Check if batch exists
        existing = supabase.table("batches")\
            .select("id")\
            .eq("id", str(batch_id))\
            .execute()
        
        if not existing.data or len(existing.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        # Cleanup related project data (projects are not cascaded by batch delete)
        teams_response = supabase.table("teams").select("id").eq("batch_id", str(batch_id)).execute()
        teams_data = teams_response.data or []

        team_ids = [team.get("id") for team in teams_data if team.get("id")]

        # Projects table has been dropped - all data is now in teams table
        # team_ids are the same as old project_ids after migration
        if team_ids:
            supabase.table("analysis_jobs").delete().in_("team_id", team_ids).execute()
            supabase.table("analysis_snapshots").delete().in_("team_id", team_ids).execute()
            supabase.table("issues").delete().in_("team_id", team_ids).execute()
            supabase.table("project_comments").delete().in_("team_id", team_ids).execute()
            supabase.table("tech_stack").delete().in_("team_id", team_ids).execute()
            supabase.table("team_members").delete().in_("team_id", team_ids).execute()
            supabase.table("mentor_team_assignments").delete().in_("team_id", team_ids).execute()
            supabase.table("students").delete().in_("team_id", team_ids).execute()

        # Delete batch (cascade will handle remaining team records)
        supabase.table("batches").delete().eq("id", str(batch_id)).execute()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete batch: {str(e)}"
        )
