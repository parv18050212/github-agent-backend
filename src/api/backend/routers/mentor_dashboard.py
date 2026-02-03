"""
Mentor Dashboard Router
Dedicated API endpoints for mentor-only access.
All endpoints require mentor role and filter data by the logged-in mentor's assignments.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from ..middleware.auth import get_current_user, AuthUser
from ..database import get_supabase
from ..crud import TeamCRUD
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
        raise HTTPException(status_code=403, detail="Mentor access required")
    return current_user


@router.get("/dashboard")
async def get_mentor_dashboard(
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get mentor's dashboard summary.
    Returns overview of assigned teams, their statuses, and key metrics.
    """
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)
    
    # Get assigned team IDs
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    
    if not team_ids:
        return {
            "totalTeams": 0,
            "teamsOnTrack": 0,
            "teamsAtRisk": 0,
            "teamsCritical": 0,
            "averageScore": 0,
            "recentActivity": []
        }
    
    # Fetch teams with project data
    teams_response = supabase.table("teams").select(
        "*, projects!projects_teams_fk(*)"
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
        
        # Get project score if available
        project = team.get("projects")
        if project:
            if isinstance(project, list):
                project = project[0] if project else None
            if project:
                analysis = project.get("analysis_result", {})
                if isinstance(analysis, str):
                    try:
                        analysis = json.loads(analysis)
                    except:
                        analysis = {}
                score = analysis.get("totalScore", 0)
                if score > 0:
                    scores.append(score)
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    return {
        "totalTeams": len(teams),
        "teamsOnTrack": on_track,
        "teamsAtRisk": at_risk,
        "teamsCritical": critical,
        "averageScore": round(avg_score, 2),
        "recentActivity": []  # Can be extended to show recent commits, etc.
    }


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
    
    # Get project IDs for these teams
    teams_query = supabase.table("teams").select("project_id").in_("id", team_ids)
    if batch_id:
        teams_query = teams_query.eq("batch_id", batch_id)
    
    teams_result = teams_query.execute()
    project_ids = [t["project_id"] for t in teams_result.data if t.get("project_id")]
    
    if not project_ids:
        return LeaderboardResponse(
            leaderboard=[],
            total=0,
            page=page,
            page_size=page_size
        )
    
    # Query projects
    query = supabase.table("projects").select("*", count="exact").in_("id", project_ids)
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
    for idx, p in enumerate(result.data):
        leaderboard_items.append(LeaderboardItem(
            rank=start + idx + 1,
            id=UUID(p["id"]),
            repo_url=p["repo_url"],
            team_name=p.get("team_name"),
            total_score=p.get("total_score", 0),
            originality_score=p.get("originality_score"),
            quality_score=p.get("quality_score"),
            security_score=p.get("security_score"),
            implementation_score=p.get("implementation_score"),
            verdict=p.get("verdict"),
            analyzed_at=p.get("analyzed_at")
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
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get aggregated report for mentor's assigned teams.
    """
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)
    
    # Get assigned team IDs
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    
    if not team_ids:
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
    
    # Fetch teams with projects
    query = supabase.table("teams").select("*, projects!projects_teams_fk(*)").in_("id", team_ids)
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
        project = team.get("projects")
        if isinstance(project, list):
            project = project[0] if project else None
        
        analysis = {}
        if project:
            analysis = project.get("analysis_result", {})
            if isinstance(analysis, str):
                try:
                    analysis = json.loads(analysis)
                except:
                    analysis = {}
        
        total_score = analysis.get("totalScore", 0)
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
            "qualityScore": analysis.get("qualityScore", 0),
            "securityScore": analysis.get("securityScore", 0),
            "healthStatus": health,
            "lastAnalyzed": project.get("created_at") if project else None
        })
    
    avg_score = sum(scores) / len(scores) if scores else 0
    
    return {
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


@router.get("/teams/{team_id}/report")
async def get_mentor_team_report(
    team_id: str = Path(..., description="Team ID"),
    current_user: AuthUser = Depends(require_mentor)
):
    """
    Get detailed report for a specific team.
    Mentor must be assigned to this team.
    """
    supabase = get_supabase()
    mentor_id = str(current_user.user_id)
    
    # Verify mentor is assigned to this team
    team_ids = TeamCRUD.get_mentor_team_ids(mentor_id)
    
    if team_id not in team_ids:
        raise HTTPException(
            status_code=403,
            detail="You are not assigned to this team"
        )
    
    # Get team with project
    team_response = supabase.table("teams").select("*, projects!projects_teams_fk(*)").eq("id", team_id).execute()
    
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = team_response.data[0]
    project = team.get("projects")
    if isinstance(project, list):
        project = project[0] if project else None
    
    analysis = {}
    if project:
        analysis = project.get("analysis_result", {})
        if isinstance(analysis, str):
            try:
                analysis = json.loads(analysis)
            except:
                analysis = {}
    
    # Get students
    students_response = supabase.table("students").select("*").eq("team_id", team_id).execute()
    students = students_response.data or []
    
    return {
        "teamId": team_id,
        "teamName": team.get("team_name"),
        "batchId": team.get("batch_id"),
        "repoUrl": team.get("repo_url"),
        "generatedAt": datetime.utcnow().isoformat(),
        "analysis": {
            "totalScore": analysis.get("totalScore", 0),
            "qualityScore": analysis.get("qualityScore", 0),
            "securityScore": analysis.get("securityScore", 0),
            "originalityScore": analysis.get("originalityScore", 0),
            "architectureScore": analysis.get("architectureScore", 0),
            "documentationScore": analysis.get("documentationScore", 0)
        },
        "students": [
            {
                "id": s.get("id"),
                "name": s.get("name"),
                "email": s.get("email"),
                "githubUsername": s.get("github_username"),
                "mentorGrade": s.get("mentor_grade"),
                "mentorFeedback": s.get("mentor_feedback"),
                "gradingDetails": s.get("grading_details") or {}
            }
            for s in students
        ],
        "healthStatus": team.get("health_status", "on_track"),
        "lastAnalyzedAt": project.get("created_at") if project else None
    }


# Grading schemas
from pydantic import BaseModel, Field

class MentorStudentGradeInput(BaseModel):
    """Input for grading a single student (mentor only)"""
    student_id: str
    mentor_grade: Optional[float] = Field(None, ge=0, le=100, description="Grade 0-100")
    mentor_feedback: Optional[str] = None
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
    supabase = get_supabase()
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
            if grade.mentor_grade is not None:
                update_data["mentor_grade"] = grade.mentor_grade
            if grade.mentor_feedback is not None:
                update_data["mentor_feedback"] = grade.mentor_feedback
            
            if update_data:
                # If grading_details is provided, we need to merge it carefully or replace it
                # For simplicity, if provided, we rely on the client to send the structure for the specific round
                # But since we want to support partial updates (e.g. only round 2), we should fetch, merge, and update.
                # However, a simple update is easier:
                # If the client sends "grading_details": {"round_1": {...}}, Supabase/Postgres JSONB update will merge at top level?
                # No, standard update replaces the column value.
                # To merge, we'd need to fetch first or use complex SQL.
                # Let's fetch the current student first to merge JSON.
                
                if grade.grading_details:
                    current_student = supabase.table("students").select("grading_details").eq("id", grade.student_id).execute()
                    if current_student.data:
                        current_details = current_student.data[0].get("grading_details") or {}
                        # Merge dictionaries (shallow merge of rounds)
                        current_details.update(grade.grading_details)
                        update_data["grading_details"] = current_details
                
                # Update grading_details first (Critical for new feature)
                if "grading_details" in update_data:
                    try:
                        supabase.table("students").update({"grading_details": update_data["grading_details"]}).eq("id", grade.student_id).execute()
                        updated_count += 1
                    except Exception as e:
                         print(f"Error updating grading_details for student {grade.student_id}: {e}")
                         errors.append(f"Failed to update grading_details: {str(e)}")
                         continue # specific failure

                # Attempt to update legacy columns (Best effort)
                legacy_data = {}
                if "mentor_grade" in update_data:
                    legacy_data["mentor_grade"] = update_data["mentor_grade"]
                if "mentor_feedback" in update_data:
                    legacy_data["mentor_feedback"] = update_data["mentor_feedback"]
                
                if legacy_data:
                    try:
                        supabase.table("students").update(legacy_data).eq("id", grade.student_id).execute()
                    except Exception as e:
                        print(f"Warning: Failed to update legacy columns for student {grade.student_id}: {e}")
                        # Do not count as failure for the request if grading_details succeeded
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

