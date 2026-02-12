"""
Mentor Dashboard Router
Dedicated API endpoints for mentor-only access.
All endpoints require mentor role and filter data by the logged-in mentor's assignments.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from time import perf_counter

from ..middleware.auth import get_current_user, AuthUser
from ..database import get_supabase, get_supabase_admin_client
from ..crud import TeamCRUD
from ..utils.cache import cache, RedisCache
from ..schemas import (
    LeaderboardResponse,
    LeaderboardItem,
    MentorReportResponse
)
from uuid import UUID


router = APIRouter(prefix="/api/mentor", tags=["Mentor Dashboard"])


def require_mentor(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency to ensure user is a mentor."""
    if current_user.role.lower() != "mentor":
        # Allow admin users with is_mentor flag
        if current_user.role.lower() == "admin":
            try:
                admin_supabase = get_supabase_admin_client()
                mentor_flag = admin_supabase.table("users").select("is_mentor").eq("id", str(current_user.user_id)).limit(1).execute()
                if mentor_flag.data and mentor_flag.data[0].get("is_mentor"):
                    return current_user
            except Exception as e:
                print(f"[Mentor Dashboard] Mentor flag lookup failed: {e}")
        raise HTTPException(status_code=403, detail="Mentor access required")
    return current_user


@router.get("/dashboard")
async def get_mentor_dashboard(
    current_user: AuthUser = Depends(require_mentor),
    no_cache: bool = Query(False, description="Bypass cache")
):
    """
    Get mentor's dashboard summary.
    Returns overview of assigned teams, their statuses, and key metrics.
    """
    start_time = perf_counter()
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)

    print(f"[Mentor Dashboard] /dashboard called for mentor_id={mentor_id}, email={current_user.email}")

    cache_key = f"hackeval:mentor:dashboard:{mentor_id}"
    if not no_cache:
        cached_response = cache.get(cache_key)
        if cached_response:
            print(f"[Mentor Dashboard] Returning cached response")
            return cached_response
    
    # Get assigned team IDs
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    print(f"[Mentor Dashboard] Found {len(team_ids)} team IDs: {team_ids}")
    
    if not team_ids:
        print(f"[Mentor Dashboard] No teams found for mentor {mentor_id}")
        empty_response = {
            "totalTeams": 0,
            "teamsOnTrack": 0,
            "teamsAtRisk": 0,
            "teamsCritical": 0,
            "averageScore": 0,
            "recentActivity": []
        }
        print(f"[Mentor Dashboard] Returning empty response: {empty_response}")
        return empty_response
    
    # Fetch teams data directly (no more project joins)
    teams_response = supabase.table("teams").select(
        "id, team_name, batch_id, health_status, total_score"
    ).in_("id", team_ids).execute()
    
    teams = teams_response.data or []
    
    # Calculate stats
    on_track = 0
    at_risk = 0
    critical = 0
    scores = []
    
    for team in teams:
        health = team.get("health_status", "on_track")
        if health == "on_track":
            on_track += 1
        elif health == "at_risk":
            at_risk += 1
        elif health == "critical":
            critical += 1
        
        # Get score directly from team
        score = team.get("total_score") or 0
        if score > 0:
            scores.append(score)
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    response = {
        "totalTeams": len(teams),
        "teamsOnTrack": on_track,
        "teamsAtRisk": at_risk,
        "teamsCritical": critical,
        "averageScore": round(avg_score, 2),
        "recentActivity": []  # Can be extended to show recent commits, etc.
    }

    cache.set(cache_key, response, RedisCache.TTL_SHORT)
    print(f"[Mentor Dashboard] /dashboard completed in {perf_counter() - start_time:.3f}s")
    return response


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_mentor_leaderboard(
    sort_by: str = Query("total_score", description="Field to sort by"),
    order: str = Query("desc", description="Sort order (asc or desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get leaderboard for mentor's assigned teams only.
    """
    import math
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)
    
    # Get assigned team IDs
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    
    if not team_ids:
        return LeaderboardResponse(
            leaderboard=[],
            total=0,
            page=page,
            page_size=page_size
        )
    
    # Get team IDs for these teams
    teams_query = supabase.table("teams").select("id").in_("id", team_ids)
    if batch_id:
        teams_query = teams_query.eq("batch_id", batch_id)
    
    teams_result = teams_query.execute()
    filtered_team_ids = [t["id"] for t in teams_result.data]
    
    if not filtered_team_ids:
        return LeaderboardResponse(
            leaderboard=[],
            total=0,
            page=page,
            page_size=page_size
        )
    
    # Query teams directly (no more projects table)
    query = supabase.table("teams").select("*", count="exact").in_("id", filtered_team_ids)
    query = query.eq("status", "completed")
    query = query.not_.is_("total_score", "null")
    
    # Pagination
    start = (page - 1) * page_size
    end = start + page_size - 1
    
    # Sorting
    desc = (order.lower() == "desc")
    query = query.range(start, end).order(sort_by, desc=desc)
    
    result = query.execute()
    total = result.count if hasattr(result, 'count') else len(result.data)
    
    # Build response
    leaderboard_items = []
    for idx, team in enumerate(result.data):
        leaderboard_items.append(LeaderboardItem(
            rank=start + idx + 1,
            id=UUID(team["id"]),
            repo_url=team["repo_url"],
            team_name=team.get("team_name"),
            total_score=team.get("total_score", 0),
            originality_score=team.get("originality_score"),
            quality_score=team.get("quality_score"),
            security_score=team.get("security_score"),
            implementation_score=team.get("implementation_score"),
            verdict=team.get("verdict"),
            analyzed_at=team.get("analyzed_at")
        ))
    
    return LeaderboardResponse(
        leaderboard=leaderboard_items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/reports")
async def get_mentor_reports(
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    no_cache: bool = Query(False, description="Bypass cache"),
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get aggregated report for mentor's assigned teams.
    """
    start_time = perf_counter()
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)

    print(f"[Mentor Dashboard] /reports called for mentor_id={mentor_id}, email={current_user.email}, batch_id={batch_id}")

    cache_key = f"hackeval:mentor:reports:{mentor_id}:{batch_id or 'all'}"
    if not no_cache:
        cached_response = cache.get(cache_key)
        if cached_response:
            print(f"[Mentor Dashboard] Returning cached response")
            return cached_response
    
    # Get assigned team IDs
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    print(f"[Mentor Dashboard] Found {len(team_ids)} team IDs: {team_ids}")
    
    if not team_ids:
        print(f"[Mentor Dashboard] No teams found for mentor {mentor_id}")
        return {
            "mentorId": mentor_id,
            "generatedAt": datetime.utcnow().isoformat(),
            "teams": [],
            "summary": {
                "totalTeams": 0,
                "averageScore": 0,
                "teamsOnTrack": 0,
                "teamsAtRisk": 0,
                "teamsCritical": 0
            }
        }
    
    # Fetch teams directly (no more project joins)
    query = supabase.table("teams").select(
        "id, team_name, batch_id, health_status, total_score, quality_score, security_score, last_analyzed_at, analyzed_at, created_at, repo_url, student_count"
    ).in_("id", team_ids)
    if batch_id:
        query = query.eq("batch_id", batch_id)
    
    teams_response = query.execute()
    teams = teams_response.data or []
    
    # Process teams
    teams_data = []
    scores = []
    on_track = 0
    at_risk = 0
    critical = 0
    
    for team in teams:
        total_score = team.get("total_score") or 0
        quality_score = team.get("quality_score") or 0
        security_score = team.get("security_score") or 0
        if total_score > 0:
            scores.append(total_score)
        
        health = team.get("health_status", "on_track")
        if health == "on_track":
            on_track += 1
        elif health == "at_risk":
            at_risk += 1
        elif health == "critical":
            critical += 1
        
        teams_data.append({
            "teamId": team["id"],
            "teamName": team.get("team_name"),
            "batchId": team.get("batch_id"),
            "totalScore": total_score,
            "qualityScore": quality_score,
            "securityScore": security_score,
            "healthStatus": health,
            "lastAnalyzed": team.get("last_analyzed_at") or team.get("analyzed_at") or team.get("created_at"),
            "repoUrl": team.get("repo_url"),
            "studentCount": team.get("student_count", 0)
        })
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    response = {
        "mentorId": mentor_id,
        "generatedAt": datetime.utcnow().isoformat(),
        "teams": teams_data,
        "summary": {
            "totalTeams": len(teams),
            "averageScore": round(avg_score, 2),
            "teamsOnTrack": on_track,
            "teamsAtRisk": at_risk,
            "teamsCritical": critical
        }
    }

    cache.set(cache_key, response, RedisCache.TTL_SHORT)
    print(f"[Mentor Dashboard] /reports completed in {perf_counter() - start_time:.3f}s")
    return response


@router.get("/teams/{team_id}/report")
async def get_mentor_team_report(
    team_id: str = Path(..., description="Team ID"),
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get detailed report for a specific team.
    Mentor must be assigned to this team.
    """
    start_time = perf_counter()
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)

    cache_key = f"hackeval:mentor:team_report:{mentor_id}:{team_id}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response
    
    # Verify mentor is assigned to this team
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    
    if team_id not in team_ids:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this team"
        )
    
    # Get team directly (no more project joins)
    team_response = supabase.table("teams").select(
        "id, team_name, batch_id, repo_url, health_status, total_score, quality_score, security_score, originality_score, engineering_score, organization_score, documentation_score, last_analyzed_at, analyzed_at, created_at, verdict, ai_pros, ai_cons"
    ).eq("id", team_id).execute()
    
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = team_response.data[0]
    
    # Get scores directly from team
    total_score = team.get("total_score") or 0
    quality_score = team.get("quality_score") or 0
    security_score = team.get("security_score") or 0
    originality_score = team.get("originality_score") or 0
    architecture_score = team.get("engineering_score") or team.get("organization_score") or 0
    documentation_score = team.get("documentation_score") or 0
    
    # Get students
    students_response = supabase.table("students").select(
        "id, name, email, github_username, grading_details"
    ).eq("team_id", team_id).execute()
    students = students_response.data or []
    
    response = {
        "teamId": team_id,
        "teamName": team.get("team_name"),
        "batchId": team.get("batch_id"),
        "repoUrl": team.get("repo_url"),
        "generatedAt": datetime.utcnow().isoformat(),
        "analysis": {
            "totalScore": total_score,
            "qualityScore": quality_score,
            "securityScore": security_score,
            "originalityScore": originality_score,
            "architectureScore": architecture_score,
            "documentationScore": documentation_score
        },
        "aiSummary": {
            "verdict": team.get("verdict"),
            "pros": team.get("ai_pros"),
            "cons": team.get("ai_cons")
        },
        "students": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "email": s.get("email"),
                "githubUsername": s.get("github_username"),
                "gradingDetails": s.get("grading_details") or {}
            }
            for s in students
        ],
        "healthStatus": team.get("health_status", "on_track"),
        "lastAnalyzedAt": team.get("last_analyzed_at") or team.get("analyzed_at") or team.get("created_at")
    }

    cache.set(cache_key, response, RedisCache.TTL_SHORT)
    print(f"[Mentor Dashboard] /teams/{team_id}/report completed in {perf_counter() - start_time:.3f}s")
    return response


@router.post("/cache/clear")
async def clear_mentor_cache(
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Clear all cache entries for the current mentor.
    Useful for debugging or forcing fresh data.
    """
    mentor_id = str(current_user.user_id)
    
    # Clear all mentor-related cache keys
    cache_keys = [
        f"hackeval:mentor:dashboard:{mentor_id}",
        f"hackeval:mentor:reports:{mentor_id}:all",
        f"hackeval:mentor:team_ids:{mentor_id}",
    ]
    
    cleared_count = 0
    for key in cache_keys:
        try:
            cache.delete(key)
            cleared_count += 1
        except Exception as e:
            print(f"[Mentor Dashboard] Failed to clear cache key {key}: {e}")
    
    print(f"[Mentor Dashboard] Cleared {cleared_count} cache entries for mentor {mentor_id}")
    
    return {
        "success": True,
        "message": f"Cleared {cleared_count} cache entries",
        "mentor_id": mentor_id
    }


@router.get("/debug/info")
async def get_mentor_debug_info(
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get debug information for the current mentor.
    Shows user info, team assignments, and cache status.
    """
    mentor_id = str(current_user.user_id)
    supabase = get_supabase()
    
    # Get team IDs (bypassing cache)
    team_ids_direct = []
    team_ids_assignments = []
    
    try:
        t_direct = supabase.table("teams").select("id, team_name").eq("mentor_id", mentor_id).execute()
        team_ids_direct = t_direct.data or []
    except Exception as e:
        print(f"[Debug] Error fetching direct teams: {e}")
    
    try:
        assignments = supabase.table("mentor_team_assignments").select("team_id, teams(id, team_name)").eq("mentor_id", mentor_id).execute()
        team_ids_assignments = assignments.data or []
    except Exception as e:
        print(f"[Debug] Error fetching assignments: {e}")
    
    # Get cached team IDs
    cache_key = f"hackeval:mentor:team_ids:{mentor_id}"
    cached_team_ids = cache.get(cache_key)
    
    return {
        "user": {
            "id": mentor_id,
            "email": current_user.email,
            "role": current_user.role,
            "full_name": current_user.full_name
        },
        "teams_via_direct_column": {
            "count": len(team_ids_direct),
            "teams": team_ids_direct
        },
        "teams_via_assignments": {
            "count": len(team_ids_assignments),
            "assignments": team_ids_assignments
        },
        "cached_team_ids": {
            "exists": cached_team_ids is not None,
            "count": len(cached_team_ids) if cached_team_ids else 0,
            "ids": cached_team_ids
        },
        "total_unique_teams": len(set(
            [t["id"] for t in team_ids_direct] +
            [a["team_id"] for a in team_ids_assignments]
        ))
    }


# Grading schemas
from pydantic import BaseModel

class MentorStudentGradeInput(BaseModel):
    """Input for grading a single student (mentor only)"""
    student_id: str
    grading_details: Optional[Dict[str, Any]] = None


@router.put("/teams/{team_id}/grades")
async def grade_team_students(
    team_id: str = Path(..., description="Team ID"),
    grades: List[MentorStudentGradeInput] = [],
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Grade students in a team (Mentor only).
    This endpoint is separate from admin grading to avoid conflicts.
    Mentors can only grade students in teams assigned to them.
    """
    supabase = get_supabase_admin_client()  # Changed from get_supabase() to bypass RLS
    mentor_id = str(current_user.user_id)
    
    # Verify mentor is assigned to this team
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    
    if team_id not in team_ids:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this team"
        )
    
    # Verify all students belong to this team
    student_ids = [g.student_id for g in grades]
    if student_ids:
        students_check = supabase.table("students").select("id").eq("team_id", team_id).in_("id", student_ids).execute()
        found_ids = {s["id"] for s in students_check.data}
        if len(found_ids) != len(student_ids):
            raise HTTPException(status_code=400, detail="One or more students do not belong to this team")
    
    # Update grades
    updated_count = 0
    errors = []
    
    print(f"Received grades update request for team {team_id} with {len(grades)} students.")
    
    for grade in grades:
        try:
            print(f"Processing student {grade.student_id}. Data: {grade.dict()}")
            update_data = {}
            if grade.grading_details:
                current_student = supabase.table("students").select("grading_details").eq("id", grade.student_id).execute()
                if current_student.data:
                    current_details = current_student.data[0].get("grading_details") or {}
                    # Merge dictionaries (shallow merge of rounds)
                    current_details.update(grade.grading_details)
                    update_data["grading_details"] = current_details

            if "grading_details" in update_data:
                try:
                    supabase.table("students").update({"grading_details": update_data["grading_details"]}).eq("id", grade.student_id).execute()
                    updated_count += 1
                except Exception as e:
                    print(f"Error updating grading_details for student {grade.student_id}: {e}")
                    errors.append(f"Failed to update grading_details: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error processing student {grade.student_id}: {e}")
            errors.append(f"Unexpected error for student {grade.student_id}: {str(e)}")
    
    if errors:
        return {
            "success": False,
            "message": f"Updated {updated_count} students with errors: {'; '.join(errors)}"
        }
    
    return {
        "success": True,
        "message": f"Successfully graded {updated_count} students"
    }

