"""
Dashboard API endpoints for admin and mentor dashboards.
Provides real-time statistics and overview for batch management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime, timedelta

from ..middleware.auth import get_current_user, AuthUser
from ..database import get_supabase, get_supabase_admin_client
from ..schemas import (
    AdminDashboardResponse,
    MentorDashboardResponse,
    UserListResponse,
    UserRoleUpdateRequest,
    UserRoleUpdateResponse
)

router = APIRouter(prefix="/api", tags=["dashboards"])


def _parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _is_active(last_activity, created_at, days: int = 7) -> bool:
    ts = _parse_timestamp(last_activity) or _parse_timestamp(created_at)
    if not ts:
        return False
    if ts.tzinfo:
        return ts >= datetime.now(ts.tzinfo) - timedelta(days=days)
    return ts >= datetime.utcnow() - timedelta(days=days)


@router.get("/admin/dashboard", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    batchId: str = Query(..., description="Batch ID to get dashboard for"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get admin dashboard overview for a specific batch.
    Admin only.
    """
    # Check admin role
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    supabase = get_supabase_admin_client()
    
    # Verify batch exists
    batch_response = supabase.table("batches").select("*").eq("id", batchId).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    batch = batch_response.data[0]
    
    # Get total teams count
    teams_response = supabase.table("teams").select("id, health_status, mentor_id, last_activity, created_at, team_name").eq("batch_id", batchId).execute()
    teams = teams_response.data
    
    # Calculate overview stats
    total_teams = len(teams)
    active_teams = len([t for t in teams if _is_active(t.get("last_activity"), t.get("created_at"))])
    inactive_teams = total_teams - active_teams
    unassigned_teams = len([t for t in teams if not t.get("mentor_id")])
    
    # Get health distribution
    health_dist = {
        "onTrack": len([t for t in teams if t.get("health_status") == "on_track"]),
        "atRisk": len([t for t in teams if t.get("health_status") == "at_risk"]),
        "critical": len([t for t in teams if t.get("health_status") == "critical"])
    }
    
    # Get total students count (from students table)
    team_ids = [t.get("id") for t in teams if t.get("id")]
    if team_ids:
        students_response = supabase.table("students").select("id, team_id").in_("team_id", team_ids).execute()
        total_students = len(students_response.data) if students_response.data else 0
    else:
        total_students = 0
    
    # Get total mentors count (unique mentors assigned to teams)
    unique_mentors = set(t.get("mentor_id") for t in teams if t.get("mentor_id"))
    total_mentors = len(unique_mentors)
    
    # Get analysis queue count (teams with status 'pending' or 'processing')
    # For now, we'll set this to 0 as we don't have an analysis queue table yet
    analysis_queue = 0
    
    # Get recent activity (last 10 activities)
    # We'll simulate this with team creation and updates
    recent_activity = []
    
    # Get recently created teams
    recent_teams = supabase.table("teams").select("id, team_name, created_at").eq("batch_id", batchId).order("created_at", desc=True).limit(5).execute()
    for team in recent_teams.data if recent_teams.data else []:
        recent_activity.append({
            "id": team["id"],
            "type": "team_created",
            "message": "New team added",
            "teamName": team["team_name"],
            "timestamp": team["created_at"]
        })
    
    # Sort by timestamp and limit to 10
    recent_activity.sort(key=lambda x: x["timestamp"], reverse=True)
    recent_activity = recent_activity[:10]
    
    # Get mentor workload
    admin_supabase = get_supabase_admin_client()
    mentor_workload = []
    for mentor_id in unique_mentors:
        # Get mentor info
        mentor_response = admin_supabase.table("users").select("id, full_name").eq("id", mentor_id).execute()
        if not mentor_response.data:
            continue
        
        mentor = mentor_response.data[0]
        
        # Get mentor's teams
        mentor_teams = [t for t in teams if t.get("mentor_id") == mentor_id]
        assigned_teams = len(mentor_teams)
        on_track = len([t for t in mentor_teams if t.get("health_status") == "on_track"])
        at_risk = len([t for t in mentor_teams if t.get("health_status") == "at_risk"])
        
        mentor_workload.append({
            "mentorId": mentor_id,
            "mentorName": mentor["full_name"],
            "assignedTeams": assigned_teams,
            "onTrack": on_track,
            "atRisk": at_risk
        })
    
    # Sort by assigned teams descending
    mentor_workload.sort(key=lambda x: x["assignedTeams"], reverse=True)
    
    return {
        "batchId": batchId,
        "batchName": batch["name"],
        "overview": {
            "totalTeams": total_teams,
            "activeTeams": active_teams,
            "inactiveTeams": inactive_teams,
            "totalMentors": total_mentors,
            "totalStudents": total_students,
            "unassignedTeams": unassigned_teams,
            "analysisQueue": analysis_queue
        },
        "healthDistribution": health_dist,
        "recentActivity": recent_activity,
        "mentorWorkload": mentor_workload
    }


@router.get("/admin/users", response_model=UserListResponse)
async def get_admin_users(
    role: Optional[str] = Query(None, description="Filter by role: admin or mentor"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1, description="Page number"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get all users with role management.
    Admin only.
    """
    # Check admin role
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    supabase = get_supabase_admin_client()
    
    # Build query
    query = supabase.table("users").select("*")
    
    # Apply filters
    if role:
        if role not in ["admin", "mentor"]:
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'mentor'")
        query = query.eq("role", role)
    
    # For search, we need to use ilike (case-insensitive LIKE)
    if search:
        # Note: Supabase doesn't support OR conditions easily, so we'll filter in Python
        all_users_response = query.execute()
        users = all_users_response.data or []
        
        # Filter by search term
        search_lower = search.lower()
        users = [
            u for u in users
            if search_lower in (u.get("full_name") or "").lower()
            or search_lower in (u.get("email") or "").lower()
        ]
    else:
        all_users_response = query.execute()
        users = all_users_response.data or []
    
    # Sort by created_at descending
    users.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    # Calculate total
    total = len(users)
    
    # Apply pagination
    start = (page - 1) * pageSize
    end = start + pageSize
    users_page = users[start:end]
    
    # Format response
    formatted_users = []
    for user in users_page:
        formatted_users.append({
            "id": user["id"],
            "email": user.get("email", ""),
            "fullName": user.get("full_name") or "",
            "role": user.get("role", "mentor"),
            "status": user.get("status", "active"),
            "lastLogin": user.get("last_login"),
            "createdAt": user.get("created_at")
        })
    
    return {
        "users": formatted_users,
        "total": total,
        "page": page,
        "pageSize": pageSize
    }


@router.put("/admin/users/{userId}/role", response_model=UserRoleUpdateResponse)
async def update_user_role(
    userId: str,
    request: UserRoleUpdateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Change user role.
    Admin only.
    """
    # Check admin role
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate role
    if request.role not in ["admin", "mentor"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be 'admin' or 'mentor'")
    
    supabase = get_supabase()
    
    # Check if user exists
    user_response = supabase.table("users").select("*").eq("id", userId).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user role
    update_response = supabase.table("users").update({
        "role": request.role,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", userId).execute()
    
    if not update_response.data:
        raise HTTPException(status_code=500, detail="Failed to update user role")
    
    updated_user = update_response.data[0]
    
    return {
        "user": {
            "id": updated_user["id"],
            "email": updated_user.get("email", ""),
            "fullName": updated_user.get("full_name", ""),
            "role": updated_user.get("role", "mentor"),
            "status": updated_user.get("status", "active"),
            "lastLogin": updated_user.get("last_login"),
            "createdAt": updated_user.get("created_at")
        },
        "message": "User role updated successfully"
    }


@router.get("/mentor/dashboard", response_model=MentorDashboardResponse)
async def get_mentor_dashboard(
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get mentor's dashboard with assigned teams overview.
    Mentor only.
    """
    mentor_id = str(current_user.user_id)
    
    supabase = get_supabase()
    
    # Get mentor info
    mentor_response = supabase.table("users").select("*").eq("id", mentor_id).execute()
    if not mentor_response.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    mentor = mentor_response.data[0]
    
    # Get assigned teams
    teams_response = supabase.table("teams").select(
        "*, batches(name)"
    ).eq("mentor_id", mentor_id).execute()
    
    teams = teams_response.data or []
    
    # Calculate overview stats
    total_teams = len(teams)
    on_track = len([t for t in teams if t.get("health_status") == "on_track"])
    at_risk = len([t for t in teams if t.get("health_status") == "at_risk"])
    critical = len([t for t in teams if t.get("health_status") == "critical"])
    
    # Format teams for response
    formatted_teams = []
    for team in teams:
        # Calculate last activity (simulated for now)
        updated_at = team.get("updated_at")
        last_activity = "Unknown"
        if updated_at:
            try:
                updated_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                time_diff = datetime.now(updated_time.tzinfo) - updated_time
                hours = int(time_diff.total_seconds() / 3600)
                if hours < 1:
                    last_activity = "Less than an hour ago"
                elif hours < 24:
                    last_activity = f"{hours} hours ago"
                else:
                    days = hours // 24
                    last_activity = f"{days} days ago"
            except:
                last_activity = "Unknown"
        
        # Get batch name
        batch_name = team.get("batches", {}).get("name", "Unknown Batch") if team.get("batches") else "Unknown Batch"
        
        formatted_teams.append({
            "id": team["id"],
            "name": team.get("team_name"),
            "batchId": team["batch_id"],
            "batchName": batch_name,
            "repoUrl": team.get("repo_url", ""),
            "healthStatus": team.get("health_status", "on_track"),
            "lastActivity": last_activity,
            "contributionBalance": team.get("contribution_balance", 0),
            "riskFlags": team.get("risk_flags", []),
            "totalScore": team.get("total_score", 0.0)
        })
    
    # Get recent activity (from teams updates)
    recent_activity = []
    recent_teams = sorted(teams, key=lambda x: x.get("updated_at", ""), reverse=True)[:5]
    
    for team in recent_teams:
        recent_activity.append({
            "teamId": team["id"],
            "teamName": team.get("team_name"),
            "type": "update",
            "message": "Team updated",
            "timestamp": team.get("updated_at", datetime.utcnow().isoformat())
        })
    
    return {
        "mentorId": mentor_id,
        "mentorName": mentor.get("full_name", ""),
        "overview": {
            "totalTeams": total_teams,
            "onTrack": on_track,
            "atRisk": at_risk,
            "critical": critical
        },
        "teams": formatted_teams,
        "recentActivity": recent_activity
    }


@router.get("/mentor/teams")
async def get_mentor_teams(
    batchId: Optional[str] = Query(None, description="Filter by batch ID"),
    healthStatus: Optional[str] = Query(None, description="Filter by health status"),
    search: Optional[str] = Query(None, description="Search by team name"),
    sort: Optional[str] = Query("name", description="Sort by: name, lastActivity, healthStatus"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get all teams assigned to mentor with optional filters.
    Mentor only.
    """
    mentor_id = str(current_user.user_id)
    
    supabase = get_supabase()
    
    # Get assigned teams
    query = supabase.table("teams").select("*, batches(name)").eq("mentor_id", mentor_id)
    
    # Apply batch filter
    if batchId:
        query = query.eq("batch_id", batchId)
    
    # Apply health status filter
    if healthStatus:
        if healthStatus not in ["on_track", "at_risk", "critical"]:
            raise HTTPException(status_code=400, detail="Invalid health status")
        query = query.eq("health_status", healthStatus)
    
    teams_response = query.execute()
    teams = teams_response.data or []
    
    # Apply search filter
    if search:
        search_lower = search.lower()
        teams = [t for t in teams if (t.get("team_name") or "").lower().find(search_lower) >= 0]
    
    # Sort teams
    if sort == "name":
        teams.sort(key=lambda x: x["name"])
    elif sort == "lastActivity":
        teams.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    elif sort == "healthStatus":
        # Sort by health status: critical, at_risk, on_track
        health_order = {"critical": 0, "at_risk": 1, "on_track": 2}
        teams.sort(key=lambda x: health_order.get(x.get("health_status", "on_track"), 3))
    
    # Format teams
    formatted_teams = []
    for team in teams:
        batch_name = team.get("batches", {}).get("name", "Unknown Batch") if team.get("batches") else "Unknown Batch"
        is_active = _is_active(team.get("last_activity"), team.get("created_at"))
        
        formatted_teams.append({
            "id": team["id"],
            "name": team.get("team_name"),
            "batchId": team["batch_id"],
            "batchName": batch_name,
            "repoUrl": team.get("repo_url", ""),
            "healthStatus": team.get("health_status", "on_track"),
            "status": "active" if is_active else "inactive",
            "contributionBalance": team.get("contribution_balance", 0),
            "totalScore": team.get("total_score", 0.0)
        })
    
    return {
        "teams": formatted_teams,
        "total": len(formatted_teams)
    }
