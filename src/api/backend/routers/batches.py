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
            # Get projects
            projects_result = supabase.table("projects")\
                .select("id, status, total_score")\
                .in_("id", [str(pid) for pid in project_ids])\
                .execute()
            
            projects = projects_result.data or []
            
            completed_projects = sum(1 for p in projects if p.get("status") == "completed")
            pending_projects = sum(1 for p in projects if p.get("status") in ["pending", "analyzing"])
            
            # Calculate average score for completed projects
            scores = [p["total_score"] for p in projects if p.get("total_score") is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
        
        return BatchStatsResponse(
            id=UUID(batch["id"]),
            name=batch["name"],
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
        
        # Delete batch (cascade will handle related records)
        result = supabase.table("batches")\
            .delete()\
            .eq("id", str(batch_id))\
            .execute()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete batch: {str(e)}"
        )
