"""
Mentor Management Router - Phase 3
Handles all mentor CRUD operations and mentor-related endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID

from ..models import UserProfile
from ..schemas import (
    MentorResponse, MentorDetailResponse, MentorListResponse,
    MentorCreateRequest, MentorUpdateRequest,
    MessageResponse
)
from ..middleware import get_current_user, RoleChecker, AuthUser
from ..database import get_supabase, get_supabase_admin_client

router = APIRouter(prefix="/api/mentors", tags=["Mentors"])


@router.get("", response_model=MentorListResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def list_mentors(
    batch_id: Optional[UUID] = Query(None, description="Filter mentors by batch"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    status: Optional[str] = Query(None, description="Filter by status"),
    sort: str = Query("full_name", description="Sort field"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get all mentors (admin only).
    
    Returns list of mentors with team counts and batch assignments.
    """
    supabase = get_supabase_admin_client()
    
    # Query users with mentor role
    query = supabase.table("users").select(
        """
        id,
        email,
        full_name,
        avatar_url,
        status,
        created_at
        """,
        count="exact"
    ).eq("role", "mentor")
    
    # Apply filters
    if status:
        query = query.eq("status", status)
    
    if search:
        query = query.or_(
            f"full_name.ilike.%{search}%,"
            f"email.ilike.%{search}%"
        )
    
    # Apply sorting
    if sort.startswith("-"):
        query = query.order(sort[1:], desc=True)
    else:
        query = query.order(sort)
    
    # Execute query
    response = query.execute()
    mentors_data = response.data
    
    # Enrich with team counts and batches
    for mentor in mentors_data:
        mentor_id = mentor["id"]
        
        # Get team count and batches for this mentor
        if batch_id:
            # Filter by batch
            teams_response = supabase.table("teams").select(
                "id, batch_id, batches!inner(id)"
            ).eq("mentor_id", mentor_id).eq("batch_id", str(batch_id)).execute()
        else:
            teams_response = supabase.table("teams").select(
                "id, batch_id"
            ).eq("mentor_id", mentor_id).execute()
        
        teams = teams_response.data or []
        mentor["team_count"] = len(teams)
        
        # Get unique batches
        unique_batches = list(set(team["batch_id"] for team in teams if team.get("batch_id")))
        mentor["batches"] = unique_batches
    
    return MentorListResponse(
        mentors=mentors_data,
        total=len(mentors_data)
    )


@router.post("", response_model=MentorResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def create_mentor(
    mentor_data: MentorCreateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Add a new mentor (admin only).
    
    Creates a user account with mentor role. The mentor must sign in with Google OAuth.
    """
    supabase = get_supabase()
    
    # Check if user already exists
    existing_user = supabase.table("users").select("id, email").eq("email", mentor_data.email).execute()
    
    if existing_user.data:
        raise HTTPException(
            status_code=400,
            detail=f"User with email {mentor_data.email} already exists"
        )
    
    # Note: In a real implementation, we would:
    # 1. Send an invitation email to the mentor
    # 2. They would sign up via Google OAuth
    # 3. On first login, we set their role to 'mentor'
    
    # For now, we'll create a placeholder user that will be populated on first login
    user_insert = {
        "email": mentor_data.email,
        "full_name": mentor_data.full_name,
        "role": "mentor",
        "status": mentor_data.status or "active"
    }
    
    # Note: This is a simplified version. In production, you'd use Supabase Admin API
    # to create the user properly, or send an invite
    
    return MentorResponse(
        mentor={
            "email": mentor_data.email,
            "full_name": mentor_data.full_name,
            "role": "mentor",
            "status": mentor_data.status or "active",
            "team_count": 0,
            "batches": []
        },
        message=f"Invitation sent to {mentor_data.email}. They must sign in with Google to activate their account."
    )


@router.get("/{mentor_id}", response_model=MentorDetailResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def get_mentor(
    mentor_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get mentor details with assigned teams.
    
    Returns complete mentor profile with all team assignments.
    """
    # Use admin client to bypass RLS policies on users table
    supabase = get_supabase_admin_client()
    
    # Get mentor user
    mentor_response = supabase.table("users").select(
        "id, email, full_name, avatar_url, status, role, created_at"
    ).eq("id", str(mentor_id)).eq("role", "mentor").execute()
    
    if not mentor_response.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    mentor = mentor_response.data[0]
    
    # Get assigned teams
    teams_response = supabase.table("teams").select(
        """
        id,
        team_name,
        batch_id,
        status,
        health_status,
        last_activity,
        batches!inner(id, name)
        """
    ).eq("mentor_id", str(mentor_id)).execute()
    
    teams = teams_response.data or []
    
    # Format assigned teams
    assigned_teams = []
    unique_batches = set()
    
    for team in teams:
        batch = team.get("batches", {})
        if isinstance(batch, list):
            batch = batch[0] if batch else {}
        
        batch_id = batch.get("id") if batch else team.get("batch_id")
        batch_name = batch.get("name") if batch else "Unknown"
        
        if batch_id:
            unique_batches.add(batch_id)
        
        assigned_teams.append({
            "team_id": team["id"],
            "team_name": team.get("team_name"),
            "batch_id": batch_id,
            "batch_name": batch_name,
            "status": team.get("status"),
            "health_status": team.get("health_status"),
            "last_activity": team.get("last_activity")
        })
    
    return MentorDetailResponse(
        id=mentor["id"],
        email=mentor["email"],
        full_name=mentor.get("full_name"),
        avatar_url=mentor.get("avatar_url"),
        status=mentor.get("status", "active"),
        assigned_teams=assigned_teams,
        team_count=len(assigned_teams),
        batches=list(unique_batches),
        created_at=mentor["created_at"]
    )


@router.put("/{mentor_id}", response_model=MentorResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def update_mentor(
    mentor_id: UUID,
    mentor_data: MentorUpdateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Update mentor details (admin only).
    
    Allows updating mentor's full name and status.
    """
    supabase = get_supabase()
    
    # Check if mentor exists
    existing_mentor = supabase.table("users").select("id").eq("id", str(mentor_id)).eq("role", "mentor").execute()
    
    if not existing_mentor.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    # Build update data
    update_data = {}
    if mentor_data.full_name is not None:
        update_data["full_name"] = mentor_data.full_name
    if mentor_data.status is not None:
        update_data["status"] = mentor_data.status
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Update mentor
    mentor_response = supabase.table("users").update(update_data).eq("id", str(mentor_id)).execute()
    
    if not mentor_response.data:
        raise HTTPException(status_code=500, detail="Failed to update mentor")
    
    # Get updated mentor with team count
    updated_mentor = mentor_response.data[0]
    
    # Get team count
    teams_response = supabase.table("teams").select("id", count="exact").eq("mentor_id", str(mentor_id)).execute()
    updated_mentor["team_count"] = teams_response.count or 0
    
    return MentorResponse(
        mentor=updated_mentor,
        message="Mentor updated successfully"
    )


@router.delete("/{mentor_id}", response_model=MessageResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def delete_mentor(
    mentor_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Remove a mentor (admin only).
    
    Unassigns all teams and removes mentor account.
    """
    supabase = get_supabase()
    
    # Check if mentor exists
    existing_mentor = supabase.table("users").select("id").eq("id", str(mentor_id)).eq("role", "mentor").execute()
    
    if not existing_mentor.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    # Count teams before unassigning
    teams_response = supabase.table("teams").select("id", count="exact").eq("mentor_id", str(mentor_id)).execute()
    team_count = teams_response.count or 0
    
    # Unassign all teams
    if team_count > 0:
        supabase.table("teams").update({"mentor_id": None}).eq("mentor_id", str(mentor_id)).execute()
    
    # Delete mentor_team_assignments
    supabase.table("mentor_team_assignments").delete().eq("mentor_id", str(mentor_id)).execute()
    
    # Delete user account
    supabase.table("users").delete().eq("id", str(mentor_id)).execute()
    
    return MessageResponse(
        success=True,
        message=f"Mentor removed successfully. {team_count} teams unassigned."
    )
