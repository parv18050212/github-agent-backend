"""
Assignment Management Router - Phase 3
Handles mentor-team assignment operations
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from uuid import UUID
from datetime import datetime

from ..schemas import (
    AssignmentCreateRequest,
    AssignmentDeleteRequest,
    AssignmentResponse,
    MessageResponse
)
from ..middleware import get_current_user, RoleChecker, AuthUser
from ..database import get_supabase

router = APIRouter(prefix="/api/assignments", tags=["Assignments"])


@router.post("", response_model=AssignmentResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def assign_teams(
    assignment_data: AssignmentCreateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Assign teams to a mentor (admin only).
    
    Creates mentor-team assignments and updates team mentor_id.
    """
    supabase = get_supabase()
    
    # Verify mentor exists
    mentor_response = supabase.table("users").select("id, email, full_name").eq(
        "id", str(assignment_data.mentor_id)
    ).eq("role", "mentor").execute()
    
    if not mentor_response.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    mentor = mentor_response.data[0]
    
    # Verify all teams exist and get their batch_ids
    team_ids_str = [str(tid) for tid in assignment_data.team_ids]
    teams_response = supabase.table("teams").select("id, team_name, batch_id").in_(
        "id", team_ids_str
    ).execute()
    
    if not teams_response.data or len(teams_response.data) != len(assignment_data.team_ids):
        found_ids = {team["id"] for team in teams_response.data} if teams_response.data else set()
        missing_ids = set(team_ids_str) - found_ids
        raise HTTPException(
            status_code=404,
            detail=f"Teams not found: {', '.join(missing_ids)}"
        )
    
    teams = teams_response.data
    
    # Update teams with mentor_id
    for team_id in team_ids_str:
        supabase.table("teams").update({
            "mentor_id": str(assignment_data.mentor_id)
        }).eq("id", team_id).execute()
    
    # Create assignment records
    assignments = []
    for team in teams:
        assignment_insert = {
            "mentor_id": str(assignment_data.mentor_id),
            "team_id": team["id"],
            "batch_id": team["batch_id"],
            "assigned_by": str(current_user.user_id)
        }
        
        # Check if assignment already exists
        existing = supabase.table("mentor_team_assignments").select("id").eq(
            "mentor_id", str(assignment_data.mentor_id)
        ).eq("team_id", team["id"]).execute()
        
        if not existing.data:
            # Create new assignment
            assignment_response = supabase.table("mentor_team_assignments").insert(
                assignment_insert
            ).execute()
            
            if assignment_response.data:
                assignment = assignment_response.data[0]
                assignments.append({
                    "id": assignment["id"],
                    "mentor_id": assignment["mentor_id"],
                    "team_id": assignment["team_id"],
                    "batch_id": assignment["batch_id"],
                    "assigned_at": assignment["assigned_at"]
                })
    
    return AssignmentResponse(
        success=True,
        message=f"{len(assignment_data.team_ids)} teams assigned to {mentor.get('full_name', mentor['email'])}",
        assignments=assignments
    )


@router.delete("", response_model=MessageResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def unassign_teams(
    assignment_data: AssignmentDeleteRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Unassign teams from a mentor (admin only).
    
    Removes mentor-team assignments and clears team mentor_id.
    """
    supabase = get_supabase()
    
    # Verify mentor exists
    mentor_response = supabase.table("users").select("id").eq(
        "id", str(assignment_data.mentor_id)
    ).eq("role", "mentor").execute()
    
    if not mentor_response.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    # Convert team IDs to strings
    team_ids_str = [str(tid) for tid in assignment_data.team_ids]
    
    # Clear mentor_id from teams
    for team_id in team_ids_str:
        supabase.table("teams").update({
            "mentor_id": None
        }).eq("id", team_id).eq("mentor_id", str(assignment_data.mentor_id)).execute()
    
    # Delete assignment records
    for team_id in team_ids_str:
        supabase.table("mentor_team_assignments").delete().eq(
            "mentor_id", str(assignment_data.mentor_id)
        ).eq("team_id", team_id).execute()
    
    return MessageResponse(
        success=True,
        message=f"{len(assignment_data.team_ids)} teams unassigned from mentor"
    )


@router.get("/mentor/{mentor_id}", response_model=dict)
async def get_mentor_assignments(
    mentor_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get all team assignments for a specific mentor.
    
    Mentors can view their own assignments, admins can view any mentor's assignments.
    """
    supabase = get_supabase()
    
    # Check authorization
    if current_user.role != "admin" and str(current_user.user_id) != str(mentor_id):
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only view your own assignments"
        )
    
    # Get assignments
    assignments_response = supabase.table("mentor_team_assignments").select(
        """
        *,
        teams!inner(id, team_name, health_status, batches!inner(id, name))
        """
    ).eq("mentor_id", str(mentor_id)).execute()
    
    assignments_data = assignments_response.data or []
    
    # Format response
    assignments = []
    for assignment in assignments_data:
        team = assignment.get("teams", {})
        if isinstance(team, list):
            team = team[0] if team else {}
        
        batch = team.get("batches", {})
        if isinstance(batch, list):
            batch = batch[0] if batch else {}
        
        assignments.append({
            "id": assignment["id"],
            "team_id": assignment["team_id"],
            "team_name": team.get("team_name"),
            "batch_id": assignment["batch_id"],
            "batch_name": batch.get("name"),
            "health_status": team.get("health_status"),
            "assigned_at": assignment["assigned_at"]
        })
    
    return {
        "mentor_id": str(mentor_id),
        "assignments": assignments,
        "total": len(assignments)
    }
