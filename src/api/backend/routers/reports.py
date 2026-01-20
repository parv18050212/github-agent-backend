"""
Reports API endpoints.
Generates comprehensive reports for batches, mentors, and teams.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
import json

from ..middleware.auth import get_current_user
from ..database import get_supabase
from ..schemas import (
    BatchReportResponse,
    MentorReportResponse,
    TeamReportResponse
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/batch/{batchId}", response_model=BatchReportResponse)
async def get_batch_report(
    batchId: str = Path(..., description="Batch ID"),
    format: Optional[str] = Query("json", description="Format: json, pdf, or csv"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate batch-wide report.
    Admin only.
    """
    # Check admin role
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    supabase = get_supabase()
    
    # Verify batch exists
    batch_response = supabase.table("batches").select("*").eq("id", batchId).execute()
    if not batch_response.data:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    batch = batch_response.data[0]
    
    # Get all teams in the batch with their project data
    teams_response = supabase.table("teams").select(
        "*, projects(*)"
    ).eq("batch_id", batchId).execute()
    
    teams = teams_response.data or []
    
    # Calculate summary statistics
    total_teams = len(teams)
    
    # Get scores from teams that have been analyzed
    scores = []
    teams_data = []
    
    for idx, team in enumerate(teams):
        # Get project analysis if it exists
        project = None
        if team.get("projects"):
            if isinstance(team["projects"], list):
                project = team["projects"][0] if team["projects"] else None
            else:
                project = team["projects"]
        
        analysis_result = {}
        if project:
            analysis_result = project.get("analysis_result", {})
            if isinstance(analysis_result, str):
                try:
                    analysis_result = json.loads(analysis_result)
                except:
                    analysis_result = {}
        
        total_score = analysis_result.get("totalScore", 0)
        if total_score > 0:
            scores.append(total_score)
        
        teams_data.append({
            "rank": idx + 1,  # Will be re-ranked after sorting
            "teamName": team["name"],
            "totalScore": total_score,
            "qualityScore": analysis_result.get("qualityScore", 0),
            "securityScore": analysis_result.get("securityScore", 0),
            "originalityScore": analysis_result.get("originalityScore", 0),
            "architectureScore": analysis_result.get("architectureScore", 0),
            "documentationScore": analysis_result.get("documentationScore", 0),
            "healthStatus": team.get("health_status", "on_track"),
            "mentorId": team.get("mentor_id"),
            "frameworks": analysis_result.get("frameworks", [])
        })
    
    # Sort teams by total score descending
    teams_data.sort(key=lambda x: x["totalScore"], reverse=True)
    
    # Update ranks
    for idx, team in enumerate(teams_data):
        team["rank"] = idx + 1
    
    # Calculate summary
    average_score = sum(scores) / len(scores) if scores else 0
    top_team = teams_data[0] if teams_data else None
    
    # Get most used technologies
    all_frameworks = []
    total_ai_usage = []
    
    for team_data in teams_data:
        frameworks = team_data.get("frameworks", [])
        if isinstance(frameworks, list):
            all_frameworks.extend(frameworks)
    
    # Count framework occurrences
    framework_counts = {}
    for fw in all_frameworks:
        framework_counts[fw] = framework_counts.get(fw, 0) + 1
    
    most_used_tech = max(framework_counts, key=framework_counts.get) if framework_counts else "Unknown"
    
    # Get AI usage statistics from teams
    for team in teams:
        project = None
        if team.get("projects"):
            if isinstance(team["projects"], list):
                project = team["projects"][0] if team["projects"] else None
            else:
                project = team["projects"]
        
        if project:
            analysis_result = project.get("analysis_result", {})
            if isinstance(analysis_result, str):
                try:
                    analysis_result = json.loads(analysis_result)
                except:
                    analysis_result = {}
            
            ai_percentage = analysis_result.get("aiGeneratedPercentage", 0)
            if ai_percentage > 0:
                total_ai_usage.append(ai_percentage)
    
    average_ai_usage = sum(total_ai_usage) / len(total_ai_usage) if total_ai_usage else 0
    
    # Count security issues
    total_security_issues = 0
    for team in teams:
        project = None
        if team.get("projects"):
            if isinstance(team["projects"], list):
                project = team["projects"][0] if team["projects"] else None
            else:
                project = team["projects"]
        
        if project:
            analysis_result = project.get("analysis_result", {})
            if isinstance(analysis_result, str):
                try:
                    analysis_result = json.loads(analysis_result)
                except:
                    analysis_result = {}
            
            security_issues = analysis_result.get("securityIssues", [])
            total_security_issues += len(security_issues) if isinstance(security_issues, list) else 0
    
    # Build response
    report = {
        "batchId": batchId,
        "batchName": batch["name"],
        "generatedAt": datetime.utcnow().isoformat(),
        "summary": {
            "totalTeams": total_teams,
            "averageScore": round(average_score, 2),
            "topTeam": top_team["teamName"] if top_team else "N/A",
            "topScore": top_team["totalScore"] if top_team else 0
        },
        "teams": teams_data,
        "insights": {
            "mostUsedTech": most_used_tech,
            "averageAiUsage": round(average_ai_usage, 2),
            "totalSecurityIssues": total_security_issues
        }
    }
    
    # Handle different formats
    if format == "pdf":
        # In production, generate PDF using ReportLab or similar
        return JSONResponse(
            content={
                "message": "PDF generation not yet implemented",
                "data": report
            }
        )
    elif format == "csv":
        # In production, generate CSV
        return JSONResponse(
            content={
                "message": "CSV generation not yet implemented",
                "data": report
            }
        )
    
    return report


@router.get("/mentor/{mentorId}", response_model=MentorReportResponse)
async def get_mentor_report(
    mentorId: str = Path(..., description="Mentor ID"),
    batchId: Optional[str] = Query(None, description="Filter by batch ID"),
    format: Optional[str] = Query("json", description="Format: json or pdf"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate report for mentor's assigned teams.
    Admin or the mentor themselves can access.
    """
    role = current_user.get("role")
    user_id = current_user.get("user_id")
    
    # Check authorization
    if role != "admin" and user_id != mentorId:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own reports"
        )
    
    supabase = get_supabase()
    
    # Verify mentor exists
    mentor_response = supabase.table("users").select("*").eq("id", mentorId).execute()
    if not mentor_response.data:
        raise HTTPException(status_code=404, detail="Mentor not found")
    
    mentor = mentor_response.data[0]
    
    # Get mentor's assigned teams
    query = supabase.table("teams").select("*, projects(*)").eq("mentor_id", mentorId)
    
    if batchId:
        query = query.eq("batch_id", batchId)
    
    teams_response = query.execute()
    teams = teams_response.data or []
    
    # Process teams data
    teams_data = []
    scores = []
    on_track_count = 0
    at_risk_count = 0
    critical_count = 0
    
    for team in teams:
        # Get project analysis
        project = None
        if team.get("projects"):
            if isinstance(team["projects"], list):
                project = team["projects"][0] if team["projects"] else None
            else:
                project = team["projects"]
        
        analysis_result = {}
        if project:
            analysis_result = project.get("analysis_result", {})
            if isinstance(analysis_result, str):
                try:
                    analysis_result = json.loads(analysis_result)
                except:
                    analysis_result = {}
        
        total_score = analysis_result.get("totalScore", 0)
        if total_score > 0:
            scores.append(total_score)
        
        health_status = team.get("health_status", "on_track")
        if health_status == "on_track":
            on_track_count += 1
        elif health_status == "at_risk":
            at_risk_count += 1
        elif health_status == "critical":
            critical_count += 1
        
        teams_data.append({
            "teamId": team["id"],
            "teamName": team["name"],
            "batchId": team["batch_id"],
            "totalScore": total_score,
            "qualityScore": analysis_result.get("qualityScore", 0),
            "securityScore": analysis_result.get("securityScore", 0),
            "healthStatus": health_status,
            "lastAnalyzed": project.get("created_at") if project else None
        })
    
    # Calculate summary
    average_score = sum(scores) / len(scores) if scores else 0
    
    report = {
        "mentorId": mentorId,
        "mentorName": mentor.get("full_name", ""),
        "generatedAt": datetime.utcnow().isoformat(),
        "teams": teams_data,
        "summary": {
            "totalTeams": len(teams),
            "averageScore": round(average_score, 2),
            "teamsOnTrack": on_track_count,
            "teamsAtRisk": at_risk_count,
            "teamsCritical": critical_count
        }
    }
    
    # Handle PDF format
    if format == "pdf":
        return JSONResponse(
            content={
                "message": "PDF generation not yet implemented",
                "data": report
            }
        )
    
    return report


@router.get("/team/{teamId}", response_model=TeamReportResponse)
async def get_team_report(
    teamId: str = Path(..., description="Team ID"),
    format: Optional[str] = Query("json", description="Format: json or pdf"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate detailed team report.
    Admin or assigned mentor only.
    """
    supabase = get_supabase()
    
    # Get team
    team_response = supabase.table("teams").select("*").eq("id", teamId).execute()
    if not team_response.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team = team_response.data[0]
    
    # Check authorization
    role = current_user.get("role")
    user_id = current_user.get("user_id")
    
    if role != "admin" and team.get("mentor_id") != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied. You can only view reports for teams assigned to you."
        )
    
    # Get project analysis
    project_id = team.get("project_id")
    
    if not project_id:
        # Return basic team info if not analyzed
        return {
            "teamId": teamId,
            "teamName": team["name"],
            "batchId": team["batch_id"],
            "generatedAt": datetime.utcnow().isoformat(),
            "analysis": {
                "totalScore": 0,
                "qualityScore": 0,
                "securityScore": 0,
                "originalityScore": 0,
                "architectureScore": 0,
                "documentationScore": 0
            },
            "commits": {
                "total": 0,
                "contributors": []
            },
            "codeMetrics": {
                "totalFiles": 0,
                "totalLinesOfCode": 0,
                "languages": []
            },
            "security": {
                "score": 0,
                "issues": []
            },
            "healthStatus": team.get("health_status", "on_track"),
            "lastAnalyzedAt": None
        }
    
    # Get project data
    project_response = supabase.table("projects").select("*").eq("id", project_id).execute()
    
    if not project_response.data:
        raise HTTPException(status_code=404, detail="Project analysis not found")
    
    project = project_response.data[0]
    analysis_result = project.get("analysis_result", {})
    
    if isinstance(analysis_result, str):
        try:
            analysis_result = json.loads(analysis_result)
        except:
            analysis_result = {}
    
    # Extract data
    commit_forensics = analysis_result.get("commitForensics", {})
    contributors = commit_forensics.get("contributors", [])
    
    # Build comprehensive report (same as analytics endpoint)
    report = {
        "teamId": teamId,
        "teamName": team["name"],
        "batchId": team["batch_id"],
        "generatedAt": datetime.utcnow().isoformat(),
        "analysis": {
            "totalScore": analysis_result.get("totalScore", 0),
            "qualityScore": analysis_result.get("qualityScore", 0),
            "securityScore": analysis_result.get("securityScore", 0),
            "originalityScore": analysis_result.get("originalityScore", 0),
            "architectureScore": analysis_result.get("architectureScore", 0),
            "documentationScore": analysis_result.get("documentationScore", 0)
        },
        "commits": {
            "total": commit_forensics.get("totalCommits", 0),
            "contributors": [
                {
                    "name": c.get("name", "Unknown"),
                    "commits": c.get("commits", 0),
                    "additions": c.get("additions", 0),
                    "deletions": c.get("deletions", 0)
                }
                for c in contributors
            ]
        },
        "codeMetrics": {
            "totalFiles": analysis_result.get("totalFiles", 0),
            "totalLinesOfCode": analysis_result.get("totalLinesOfCode", 0),
            "languages": analysis_result.get("languages", []),
            "techStack": analysis_result.get("frameworks", []),
            "architecturePattern": analysis_result.get("architecturePattern", "Unknown")
        },
        "security": {
            "score": analysis_result.get("securityScore", 0),
            "issues": analysis_result.get("securityIssues", []),
            "secretsDetected": analysis_result.get("secretsDetected", 0)
        },
        "aiAnalysis": {
            "aiGeneratedPercentage": analysis_result.get("aiGeneratedPercentage", 0),
            "verdict": analysis_result.get("aiVerdict", "Unknown"),
            "strengths": analysis_result.get("strengths", []),
            "improvements": analysis_result.get("improvements", [])
        },
        "healthStatus": team.get("health_status", "on_track"),
        "riskFlags": team.get("risk_flags", []),
        "lastAnalyzedAt": project.get("created_at")
    }
    
    # Handle PDF format
    if format == "pdf":
        return JSONResponse(
            content={
                "message": "PDF generation not yet implemented",
                "data": report
            }
        )
    
    return report
