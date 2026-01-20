"""
Team Management Router - Phase 2
Handles all team CRUD operations and team-related endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from typing import List, Optional
from uuid import UUID
from datetime import datetime
import csv
import io

from ..models import (
    Team, TeamCreate, TeamUpdate, TeamWithDetails,
    Student, StudentCreate,
    TeamList, PaginatedResponse
)
from ..schemas import (
    TeamResponse, TeamDetailResponse, TeamListResponse,
    TeamCreateRequest, TeamUpdateRequest,
    BulkUploadResponse, AnalysisJobResponse,
    MessageResponse, TeamAssignRequest
)
from ..middleware import get_current_user, RoleChecker, AuthUser
from ..database import get_supabase, get_supabase_admin_client

router = APIRouter(prefix="/api/teams", tags=["Teams"])


@router.get("", response_model=TeamListResponse)
async def list_teams(
    batch_id: Optional[UUID] = Query(None, description="Filter by batch ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    mentor_id: Optional[UUID] = Query(None, description="Filter by assigned mentor"),
    search: Optional[str] = Query(None, description="Search by team name or repo URL"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort: str = Query("name", description="Sort field"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get list of teams with filtering and pagination.
    
    - **Admin**: Can see all teams, requires batch_id parameter
    - **Mentor**: Only sees assigned teams
    """
    # Debug logging
    print(f"[Teams API] list_teams called")
    print(f"[Teams API] current_user.user_id: {current_user.user_id}")
    print(f"[Teams API] current_user.email: {current_user.email}")
    print(f"[Teams API] current_user.role: {current_user.role}")
    print(f"[Teams API] batch_id param: {batch_id}")
    
    supabase = get_supabase()
    
    # Build query
    query = supabase.table("teams").select(
        """
        *,
        batches!inner(id, name, semester, year),
        students(count),
        projects(id, total_score, status, last_analyzed_at),
        team_members:projects(team_members(count))
        """,
        count="exact"
    )
    
    # Role-based filtering
    if current_user.role == "mentor":
        # Mentors only see their assigned teams
        query = query.eq("mentor_id", str(current_user.user_id))
    else:
        # Admins must specify batch_id
        if not batch_id:
            raise HTTPException(
                status_code=400,
                detail="batch_id is required for admin users"
            )
        query = query.eq("batch_id", str(batch_id))
    
    # Apply filters
    # Special handling for "unassigned" status - filter by mentor_id IS NULL
    if status == "unassigned":
        query = query.is_("mentor_id", "null")
    elif status:
        query = query.eq("status", status)
    
    if mentor_id:
        query = query.eq("mentor_id", str(mentor_id))
    
    if search:
        query = query.or_(
            f"team_name.ilike.%{search}%,"
            f"projects.repo_url.ilike.%{search}%"
        )
    
    # Apply sorting (map frontend field names to database columns)
    sort_field = sort
    if sort == "name" or sort == "-name":
        # Frontend uses "name" but database has "team_name"
        sort_field = sort.replace("name", "team_name")
    
    if sort_field.startswith("-"):
        query = query.order(sort_field[1:], desc=True)
    else:
        query = query.order(sort_field)
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)
    
    # Execute query
    response = query.execute()
    
    teams = response.data
    total = response.count

    # Debug logging for query results
    print(f"[Teams API] Query returned {len(teams)} teams, total count: {total}")
    if current_user.role == "mentor":
        print(f"[Teams API] Mentor filter applied with mentor_id: {current_user.user_id}")

    mentor_ids = {str(team.get("mentor_id")) for team in teams if team.get("mentor_id")}
    mentor_lookup = {}

    if mentor_ids:
        admin_supabase = get_supabase_admin_client()
        mentor_response = admin_supabase.table("users").select("id, full_name, email").in_(
            "id", list(mentor_ids)
        ).execute()
        for mentor in mentor_response.data or []:
            mentor_lookup[str(mentor.get("id"))] = mentor.get("full_name") or mentor.get("email")

    for team in teams:
        mentor_id = team.get("mentor_id")
        team["mentor_name"] = mentor_lookup.get(str(mentor_id)) if mentor_id else None
    
    return TeamListResponse(
        teams=teams,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )


@router.post("", response_model=TeamResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def create_team(
    team_data: TeamCreateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Create a new team (admin only).
    
    Creates team with students and optionally links to a project.
    """
    supabase = get_supabase()
    
    # Verify batch exists
    batch_response = supabase.table("batches").select("id").eq("id", str(team_data.batch_id)).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Create team
    team_insert = {
        "batch_id": str(team_data.batch_id),
        "team_name": team_data.name,
        "health_status": "on_track",
        "student_count": len(team_data.students) if team_data.students else 0
    }
    
    team_response = supabase.table("teams").insert(team_insert).execute()
    
    if not team_response.data:
        raise HTTPException(status_code=500, detail="Failed to create team")
    
    team = team_response.data[0]
    team_id = team["id"]
    
    # Create project if repo URL provided
    if team_data.repo_url:
        project_insert = {
            "team_id": team_id,
            "batch_id": str(team_data.batch_id),
            "repo_url": team_data.repo_url,
            "description": team_data.description or "",
            "status": "pending"
        }
        
        project_response = supabase.table("projects").insert(project_insert).execute()
        
        if project_response.data:
            # Update team with project_id
            supabase.table("teams").update({
                "project_id": project_response.data[0]["id"]
            }).eq("id", team_id).execute()
    
    # Create students
    if team_data.students:
        students_insert = [
            {
                "team_id": team_id,
                "name": student.name,
                "email": student.email,
                "github_username": student.github_username
            }
            for student in team_data.students
        ]
        
        supabase.table("students").insert(students_insert).execute()
    
    # Fetch complete team data
    team_detail = supabase.table("teams").select(
        """
        *,
        batches(id, name, semester, year),
        students(*),
        projects(*)
        """
    ).eq("id", team_id).execute()
    
    return TeamResponse(
        team=team_detail.data[0],
        message="Team created successfully"
    )


@router.post("/{team_id}/assign", response_model=MessageResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def assign_team_to_mentor(
    team_id: UUID,
    assignment: TeamAssignRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Assign a single team to a mentor (admin only).
    """
    supabase = get_supabase_admin_client()

    # Verify team exists
    team_response = supabase.table("teams").select("id, team_name, batch_id").eq("id", str(team_id)).execute()
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")

    team = team_response.data[0]

    # Verify mentor exists
    mentor_response = supabase.table("users").select("id, email, full_name").eq(
        "id", str(assignment.mentor_id)
    ).eq("role", "mentor").execute()

    if not mentor_response.data:
        raise HTTPException(status_code=404, detail="Mentor not found")

    # Update team mentor_id
    supabase.table("teams").update({
        "mentor_id": str(assignment.mentor_id)
    }).eq("id", str(team_id)).execute()

    # Create assignment record if missing
    existing = supabase.table("mentor_team_assignments").select("id").eq(
        "mentor_id", str(assignment.mentor_id)
    ).eq("team_id", str(team_id)).execute()

    if not existing.data:
        supabase.table("mentor_team_assignments").insert({
            "mentor_id": str(assignment.mentor_id),
            "team_id": str(team_id),
            "batch_id": team.get("batch_id"),
            "assigned_by": str(current_user.user_id)
        }).execute()

    mentor = mentor_response.data[0]
    mentor_name = mentor.get("full_name") or mentor.get("email") or "mentor"

    return MessageResponse(
        success=True,
        message=f"Assigned {team.get('team_name', 'team')} to {mentor_name}"
    )


@router.post("/bulk-import", response_model=BulkUploadResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def bulk_import_teams_with_mentors(
    file: UploadFile = File(...),
    batch_id: UUID = Query(..., description="Batch ID for all teams"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Bulk import teams with mentor assignment via CSV or Excel (admin only).
    
    Supported formats: .csv, .xlsx
    
    CSV Format (Option A - with mentor):
    team_name,repo_url,mentor_email
    Team Alpha,https://github.com/org/alpha,drsmith@university.edu
    
    CSV Format (Option B - without mentor):
    team_name,repo_url
    Team Alpha,https://github.com/org/alpha
    
    Excel Format:
    Columns: Team Number, Team Name, Project Name, Github Link, etc.
    Maps: Team Name -> team_name, Github Link -> repo_url
    """
    supabase = get_supabase()
    
    # Verify batch exists
    batch_response = supabase.table("batches").select("id, start_date").eq("id", str(batch_id)).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Determine file type and parse accordingly
    contents = await file.read()
    rows = []
    
    if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
        # Parse Excel file
        import openpyxl
        from io import BytesIO
        
        wb = openpyxl.load_workbook(BytesIO(contents))
        ws = wb.active
        
        # Get headers from first row
        headers = [cell.value for cell in ws[1]]
        
        # Map column indices
        team_name_col = None
        repo_url_col = None
        mentor_email_col = None
        
        # Support multiple header variations
        for i, header in enumerate(headers):
            if header:
                header_lower = str(header).lower().strip()
                if 'team name' in header_lower or 'teamname' in header_lower:
                    team_name_col = i
                elif 'github' in header_lower or 'repo' in header_lower or 'repository' in header_lower:
                    repo_url_col = i
                elif 'mentor' in header_lower and 'email' in header_lower:
                    mentor_email_col = i
        
        if team_name_col is None or repo_url_col is None:
            raise HTTPException(
                status_code=400, 
                detail="Excel file must contain 'Team Name' and 'Github Link' columns"
            )
        
        # Convert Excel rows to dict format
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[team_name_col] and row[repo_url_col]:
                row_dict = {
                    'team_name': str(row[team_name_col]).strip() if row[team_name_col] else '',
                    'repo_url': str(row[repo_url_col]).strip() if row[repo_url_col] else ''
                }
                if mentor_email_col is not None and row[mentor_email_col]:
                    row_dict['mentor_email'] = str(row[mentor_email_col]).strip()
                rows.append(row_dict)
    else:
        # Parse CSV file
        csv_file = io.StringIO(contents.decode("utf-8"))
        csv_reader = csv.DictReader(csv_file)
        rows = list(csv_reader)
    
    successful = 0
    failed = 0
    errors = []
    created_teams = []
    
    # Get all mentors for email lookup
    mentors_response = supabase.table("users").select("id, email").eq("role", "mentor").execute()
    mentor_map = {m["email"]: m["id"] for m in mentors_response.data}
    
    for row_num, row in enumerate(rows, start=2):  # Start at 2 (header is row 1)
        try:
            team_name = row.get("team_name", "").strip()
            repo_url = row.get("repo_url", "").strip()
            mentor_email = row.get("mentor_email", "").strip() if "mentor_email" in row else None
            
            if not team_name:
                raise ValueError("Team name is required")
            
            if not repo_url:
                raise ValueError("Repository URL is required")
            
            # Validate GitHub URL
            if 'github.com' not in repo_url.lower():
                raise ValueError("Only GitHub repositories are supported")
            
            # Extract member names from team_name (separated by newlines or commas)
            member_names = []
            if '\n' in team_name:
                # Excel format with newlines
                member_names = [name.strip() for name in team_name.split('\n') if name.strip()]
            elif ',' in team_name:
                # CSV format with commas
                member_names = [name.strip() for name in team_name.split(',') if name.strip()]
            else:
                # Single member or team name
                member_names = [team_name]
            
            # Use first member name as simplified team name if multiple members
            display_team_name = member_names[0] if len(member_names) == 1 else f"Team {row_num - 1}"
            
            # Lookup mentor if provided
            mentor_id = None
            if mentor_email:
                mentor_id = mentor_map.get(mentor_email)
                if not mentor_id:
                    raise ValueError(f"Mentor not found: {mentor_email}")
            
            # Create team
            team_insert = {
                "batch_id": str(batch_id),
                "team_name": display_team_name,
                "repo_url": repo_url,
                "mentor_id": mentor_id,
                "health_status": "on_track",
                "student_count": len(member_names)
            }
            
            team_response = supabase.table("teams").insert(team_insert).execute()
            team = team_response.data[0]
            team_id = team["id"]
            
            # Create project
            project_insert = {
                "team_id": team_id,
                "batch_id": str(batch_id),
                "repo_url": repo_url,
                "description": f"Project for {display_team_name}",
                "status": "pending"
            }
            
            project_response = supabase.table("projects").insert(project_insert).execute()
            project_id = None
            
            if project_response.data:
                project_id = project_response.data[0]["id"]
                
                # Update team with project_id
                supabase.table("teams").update({
                    "project_id": project_id
                }).eq("id", team_id).execute()
                
                # Create team members linked to project
                for member_name in member_names:
                    member_insert = {
                        "project_id": project_id,
                        "name": member_name,
                        "commits": 0,
                        "contribution_pct": 0.0
                    }
                    supabase.table("team_members").insert(member_insert).execute()
                
                # Create mentor assignment if mentor provided
                if mentor_id:
                    assignment_insert = {
                        "mentor_id": mentor_id,
                        "team_id": team_id,
                        "batch_id": str(batch_id)
                    }
                    supabase.table("mentor_team_assignments").insert(assignment_insert).execute()
            
            created_teams.append(team)
            successful += 1
            
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "teamName": row.get("team_name", ""),
                "error": str(e)
            })
    
    return BulkUploadResponse(
        successful=successful,
        failed=failed,
        total=successful + failed,
        errors=errors,
        teams=created_teams,
        message=f"Bulk import completed: {successful} successful, {failed} failed"
    )


@router.post("/batch-upload", response_model=BulkUploadResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def bulk_upload_teams(
    file: UploadFile = File(...),
    batch_id: UUID = Query(..., description="Batch ID for all teams"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Bulk upload teams via CSV (admin only).
    
    CSV Format:
    teamName,repoUrl,description,student1Name,student1Email,student2Name,student2Email,...
    """
    supabase = get_supabase()
    
    # Verify batch exists
    batch_response = supabase.table("batches").select("id").eq("id", str(batch_id)).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Read CSV
    contents = await file.read()
    csv_file = io.StringIO(contents.decode("utf-8"))
    csv_reader = csv.DictReader(csv_file)
    
    successful = 0
    failed = 0
    errors = []
    created_teams = []
    
    for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (header is row 1)
        try:
            team_name = row.get("teamName", "").strip()
            repo_url = row.get("repoUrl", "").strip()
            description = row.get("description", "").strip()
            
            if not team_name:
                raise ValueError("Team name is required")
            
            # Extract students (up to 6 students)
            students = []
            for i in range(1, 7):
                student_name = row.get(f"student{i}Name", "").strip()
                student_email = row.get(f"student{i}Email", "").strip()
                
                if student_name and student_email:
                    students.append({
                        "name": student_name,
                        "email": student_email
                    })
            
            # Create team
            team_insert = {
                "batch_id": str(batch_id),
                "team_name": team_name,
                "health_status": "on_track",
                "student_count": len(students)
            }
            
            team_response = supabase.table("teams").insert(team_insert).execute()
            team = team_response.data[0]
            team_id = team["id"]
            
            # Create project if repo URL provided
            if repo_url:
                project_insert = {
                    "team_id": team_id,
                    "batch_id": str(batch_id),
                    "repo_url": repo_url,
                    "description": description,
                    "status": "pending"
                }
                
                project_response = supabase.table("projects").insert(project_insert).execute()
                
                if project_response.data:
                    supabase.table("teams").update({
                        "project_id": project_response.data[0]["id"]
                    }).eq("id", team_id).execute()
            
            # Create students
            if students:
                students_insert = [
                    {
                        "team_id": team_id,
                        "name": s["name"],
                        "email": s["email"]
                    }
                    for s in students
                ]
                
                supabase.table("students").insert(students_insert).execute()
            
            created_teams.append(team)
            successful += 1
            
        except Exception as e:
            failed += 1
            errors.append({
                "row": row_num,
                "teamName": row.get("teamName", ""),
                "error": str(e)
            })
    
    return BulkUploadResponse(
        successful=successful,
        failed=failed,
        total=successful + failed,
        errors=errors,
        teams=created_teams,
        message=f"Batch upload completed: {successful} successful, {failed} failed"
    )


@router.get("/{team_id}")
async def get_team(
    team_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get detailed team information.
    
    Returns complete team data including students, project analysis, team members, and health status.
    Frontend expects: team_name, repo_url, batches, projects, team_members
    """
    supabase = get_supabase()
    
    # Fetch team with all related data
    team_response = supabase.table("teams").select(
        """
        *,
        batches(id, name, semester, year),
        students(*),
        projects(*)
        """
    ).eq("id", team_id).execute()
    
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = team_response.data[0]
    
    # Check authorization
    if current_user.role == "mentor":
        if team.get("mentor_id") != str(current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You are not assigned to this team"
            )
    
    # Fetch team members if project exists
    team_members = []
    project = team.get("projects")
    
    if project:
        project_id = project[0]["id"] if isinstance(project, list) else project["id"]
        members_response = supabase.table("team_members").select("*").eq("project_id", project_id).execute()
        team_members = members_response.data or []
    
    # Add team_members to response
    team["team_members"] = team_members
    
    # Ensure batches is always an object (not None)
    if not team.get("batches"):
        team["batches"] = {
            "id": team["batch_id"],
            "name": "Unknown Batch",
            "semester": "",
            "year": 0
        }
    
    return team


@router.put("/{team_id}", response_model=TeamResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def update_team(
    team_id: UUID,
    team_data: TeamUpdateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Update team details (admin only).
    
    Allows updating team name, description, status, and health status.
    """
    supabase = get_supabase()
    
    # Check if team exists
    existing_team = supabase.table("teams").select("id").eq("id", str(team_id)).execute()
    if not existing_team.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Build update data
    update_data = {}
    if team_data.name is not None:
        update_data["team_name"] = team_data.name
    if team_data.status is not None:
        update_data["status"] = team_data.status
    if team_data.health_status is not None:
        update_data["health_status"] = team_data.health_status
    if team_data.risk_flags is not None:
        update_data["risk_flags"] = team_data.risk_flags
    
    # Update team
    team_response = supabase.table("teams").update(update_data).eq("id", str(team_id)).execute()
    
    # Update project if description provided
    if team_data.description is not None:
        supabase.table("projects").update({
            "description": team_data.description
        }).eq("team_id", str(team_id)).execute()
    
    # Fetch updated team
    updated_team = supabase.table("teams").select(
        """
        *,
        batches(id, name, semester, year),
        students(*),
        projects(*)
        """
    ).eq("id", str(team_id)).execute()
    
    return TeamResponse(
        team=updated_team.data[0],
        message="Team updated successfully"
    )


@router.delete("/{team_id}", response_model=MessageResponse, dependencies=[Depends(RoleChecker(["admin"]))])
async def delete_team(
    team_id: UUID,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Delete a team and its associated data (admin only).
    
    Cascades to delete students, project, and assignments.
    """
    supabase = get_supabase()
    
    # Check if team exists
    existing_team = supabase.table("teams").select("id, project_id").eq("id", str(team_id)).execute()
    if not existing_team.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Delete team (cascade will handle students and assignments)
    supabase.table("teams").delete().eq("id", str(team_id)).execute()
    
    return MessageResponse(
        success=True,
        message="Team deleted successfully"
    )


@router.get("/{team_id}/progress")
async def get_team_progress(
    team_id: int,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get weekly progress snapshots for a team.
    
    Returns historical analysis data showing improvement over time.
    """
    supabase = get_supabase()
    
    # Verify team exists and check authorization
    team_response = supabase.table("teams").select(
        "id, team_name, batch_id, mentor_id"
    ).eq("id", str(team_id)).execute()
    
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = team_response.data[0]
    
    # Check authorization
    if current_user.role == "mentor":
        if team.get("mentor_id") != str(current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You are not assigned to this team"
            )
    
    # Get all snapshots for this team
    snapshots_response = supabase.table("analysis_snapshots").select(
        """
        *,
        batch_analysis_runs(run_number, started_at, completed_at)
        """
    ).eq("team_id", str(team_id)).order("run_number", desc=False).execute()
    
    snapshots = snapshots_response.data or []
    
    # Calculate weekly trends
    weekly_data = []
    for snapshot in snapshots:
        run_info = snapshot.get("batch_analysis_runs", {})
        
        weekly_data.append({
            "week": snapshot["run_number"],
            "total_score": round(snapshot.get("total_score") or 0, 2),
            "originality_score": round(snapshot.get("originality_score") or 0, 2),
            "quality_score": round(snapshot.get("quality_score") or 0, 2),
            "security_score": round(snapshot.get("security_score") or 0, 2),
            "effort_score": round(snapshot.get("effort_score") or 0, 2),
            "commit_count": snapshot.get("commit_count", 0),
            "lines_of_code": snapshot.get("lines_of_code", 0),
            "analyzed_at": snapshot.get("analyzed_at"),
            "run_completed_at": run_info.get("completed_at") if isinstance(run_info, dict) else None
        })
    
    # Calculate improvement from previous week
    improvement = 0
    if len(weekly_data) >= 2:
        latest = weekly_data[-1]
        previous = weekly_data[-2]
        improvement = latest["total_score"] - previous["total_score"]
    
    return {
        "team_id": str(team_id),
        "team_name": team["team_name"],
        "batch_id": team["batch_id"],
        "total_weeks": len(weekly_data),
        "current_score": weekly_data[-1]["total_score"] if weekly_data else 0,
        "improvement": round(improvement, 2),
        "weekly_data": weekly_data
    }


@router.post("/{team_id}/analyze", response_model=AnalysisJobResponse)
async def analyze_team(
    team_id: UUID,
    force: bool = Query(False, description="Force re-analysis even if already analyzed"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Trigger analysis for a team's repository.
    
    Creates an analysis job and queues it for processing.
    """
    supabase = get_supabase()
    
    # Get team with project
    team_response = supabase.table("teams").select(
        "*, projects(*)"
    ).eq("id", str(team_id)).execute()
    
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = team_response.data[0]
    
    # Check authorization
    if current_user.role == "mentor":
        if team.get("mentor_id") != str(current_user.user_id):
            raise HTTPException(
                status_code=403,
                detail="Access denied: You are not assigned to this team"
            )
    
    # Check if project exists
    project = team.get("projects")
    if not project:
        raise HTTPException(status_code=404, detail="Team has no associated project")
    
    project_id = project[0]["id"] if isinstance(project, list) else project["id"]
    
    # Check if already analyzed
    if not force and project.get("status") == "completed":
        return AnalysisJobResponse(
            job_id=None,
            project_id=project_id,
            status="already_analyzed",
            message="Project already analyzed. Use force=true to re-analyze."
        )
    
    # Create analysis job
    job_insert = {
        "project_id": project_id,
        "status": "queued",
        "requested_by": str(current_user.user_id)
    }
    
    job_response = supabase.table("analysis_jobs").insert(job_insert).execute()
    
    if not job_response.data:
        raise HTTPException(status_code=500, detail="Failed to create analysis job")
    
    job = job_response.data[0]
    
    # Update project status
    supabase.table("projects").update({
        "status": "queued"
    }).eq("id", project_id).execute()
    
    return AnalysisJobResponse(
        job_id=job["id"],
        project_id=project_id,
        status="queued",
        message="Analysis queued successfully"
    )
