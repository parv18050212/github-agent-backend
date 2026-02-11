"""
Historical Analysis Data Management
Handles 7-day automatic re-analysis and data snapshots
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from datetime import datetime, timedelta
from uuid import uuid4

from ..middleware.auth import get_current_user, AuthUser, RoleChecker
from ..database import get_supabase_admin_client

router = APIRouter(prefix="/api/analysis/history", tags=["analysis-history"])


@router.get("/team/{team_id}/snapshots")
async def get_team_analysis_history(
    team_id: str,
    limit: int = Query(10, ge=1, le=50),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Get historical analysis snapshots for a team (weekly progression).
    Shows score trends over time.
    """
    supabase = get_supabase_admin_client()
    
    # Verify team access
    team = supabase.table("teams").select("*").eq("id", team_id).execute()
    if not team.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Get snapshots ordered by run_number (most recent first)
    snapshots = supabase.table("analysis_snapshots").select(
        "*, batch_analysis_runs!inner(run_number, started_at, completed_at)"
    ).eq("team_id", team_id).order("run_number", desc=True).limit(limit).execute()
    
    # Get current/latest scores from teams table (projects table has been dropped)
    current = supabase.table("teams").select(
        "total_score, quality_score, security_score, originality_score, "
        "architecture_score, documentation_score, last_analyzed_at"
    ).eq("id", team_id).execute()
    
    results = []
    
    # Add current state as "Run 0" if exists
    if current.data:
        curr = current.data[0]
        results.append({
            "runNumber": 0,
            "runLabel": "Current",
            "analyzedAt": curr.get("last_analyzed_at"),
            "scores": {
                "total": curr.get("total_score"),
                "quality": curr.get("quality_score"),
                "security": curr.get("security_score"),
                "originality": curr.get("originality_score"),
                "architecture": curr.get("architecture_score"),
                "documentation": curr.get("documentation_score")
            },
            "isCurrent": True
        })
    
    # Add historical snapshots
    for snapshot in snapshots.data or []:
        run_info = snapshot.get("batch_analysis_runs", {})
        results.append({
            "runNumber": snapshot["run_number"],
            "runLabel": f"Week {snapshot['run_number']}",
            "analyzedAt": snapshot.get("analyzed_at") or run_info.get("completed_at"),
            "scores": {
                "total": snapshot.get("total_score"),
                "quality": snapshot.get("quality_score"),
                "security": snapshot.get("security_score"),
                "originality": snapshot.get("originality_score"),
                "architecture": snapshot.get("architecture_score"),
                "documentation": snapshot.get("documentation_score")
            },
            "metadata": {
                "commitCount": snapshot.get("commit_count"),
                "fileCount": snapshot.get("file_count"),
                "linesOfCode": snapshot.get("lines_of_code"),
                "issueCount": snapshot.get("issue_count")
            },
            "isCurrent": False
        })
    
    # Calculate improvements
    for i in range(len(results) - 1):
        curr_score = results[i]["scores"]["total"]
        prev_score = results[i + 1]["scores"]["total"]
        
        if curr_score is not None and prev_score is not None:
            improvement = curr_score - prev_score
            improvement_pct = (improvement / prev_score * 100) if prev_score > 0 else 0
            
            results[i]["improvement"] = {
                "absolute": round(improvement, 2),
                "percentage": round(improvement_pct, 1),
                "trend": "up" if improvement > 0 else "down" if improvement < 0 else "stable"
            }
    
    return {
        "teamId": team_id,
        "snapshots": results,
        "totalRuns": len(results),
        "oldestRun": results[-1]["analyzedAt"] if results else None,
        "latestRun": results[0]["analyzedAt"] if results else None
    }


@router.get("/batch/{batch_id}/comparison")
async def get_batch_weekly_comparison(
    batch_id: str,
    run_number_1: int = Query(..., description="First run number to compare"),
    run_number_2: int = Query(..., description="Second run number to compare"),
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Compare two analysis runs for a batch.
    Useful for mentors to see which teams improved/declined.
    """
    supabase = get_supabase_admin_client()
    
    # Get snapshots for both runs
    snapshots_1 = supabase.table("analysis_snapshots").select(
        "team_id, total_score, teams!inner(team_name)"
    ).eq("batch_id", batch_id).eq("run_number", run_number_1).execute()
    
    snapshots_2 = supabase.table("analysis_snapshots").select(
        "team_id, total_score"
    ).eq("batch_id", batch_id).eq("run_number", run_number_2).execute()
    
    # Build lookup for run 2 scores
    run2_scores = {s["team_id"]: s["total_score"] for s in snapshots_2.data or []}
    
    # Compare
    comparisons = []
    for snap1 in snapshots_1.data or []:
        team_id = snap1["team_id"]
        score1 = snap1["total_score"]
        score2 = run2_scores.get(team_id)
        
        if score1 is not None and score2 is not None:
            diff = score1 - score2
            diff_pct = (diff / score2 * 100) if score2 > 0 else 0
            
            comparisons.append({
                "teamId": team_id,
                "teamName": snap1.get("teams", {}).get("team_name", "Unknown"),
                "run1Score": score1,
                "run2Score": score2,
                "difference": round(diff, 2),
                "differencePercentage": round(diff_pct, 1),
                "trend": "improved" if diff > 0 else "declined" if diff < 0 else "stable"
            })
    
    # Sort by improvement (descending)
    comparisons.sort(key=lambda x: x["difference"], reverse=True)
    
    return {
        "batchId": batch_id,
        "run1": run_number_1,
        "run2": run_number_2,
        "teams": comparisons,
        "summary": {
            "totalTeams": len(comparisons),
            "improved": sum(1 for c in comparisons if c["trend"] == "improved"),
            "declined": sum(1 for c in comparisons if c["trend"] == "declined"),
            "stable": sum(1 for c in comparisons if c["trend"] == "stable"),
            "avgImprovement": round(sum(c["difference"] for c in comparisons) / len(comparisons), 2) if comparisons else 0
        }
    }


@router.post("/snapshot/create", dependencies=[Depends(RoleChecker(["admin"]))])
async def create_analysis_snapshot(
    team_id: str,
    run_number: int,
    batch_run_id: str,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Manually create a snapshot from current project data.
    Used by Celery worker after completing analysis.
    
    This preserves the current state before the next 7-day re-analysis.
    """
    supabase = get_supabase_admin_client()
    
    # Get current team data (projects table has been dropped and merged into teams)
    team = supabase.table("teams").select(
        "id, total_score, originality_score, quality_score, security_score, "
        "effort_score, implementation_score, engineering_score, organization_score, "
        "documentation_score, total_commits, report_json"
    ).eq("id", team_id).execute()
    
    if not team.data:
        raise HTTPException(status_code=404, detail="Team not found")
    
    team_data = team.data[0]
    report_json = team_data.get("report_json", {})
    
    # Extract metadata from report
    structure = report_json.get("structure", {})
    
    snapshot_data = {
        "id": str(uuid4()),
        "team_id": team_id,
        "batch_run_id": batch_run_id,
        "project_id": team_data["id"],  # Keep for backward compatibility
        "run_number": run_number,
        
        # Scores
        "total_score": team_data.get("total_score"),
        "originality_score": team_data.get("originality_score"),
        "quality_score": team_data.get("quality_score"),
        "security_score": team_data.get("security_score"),
        "effort_score": team_data.get("effort_score"),
        "implementation_score": team_data.get("implementation_score"),
        "engineering_score": team_data.get("engineering_score"),
        "organization_score": team_data.get("organization_score"),
        "documentation_score": team_data.get("documentation_score"),
        
        # Metadata
        "commit_count": team_data.get("total_commits") or report_json.get("total_commits", 0),
        "file_count": structure.get("file_count", 0),
        "lines_of_code": structure.get("loc", 0),
        "tech_stack_count": len(report_json.get("stack", [])),
        "issue_count": len(report_json.get("security", {}).get("leaked_keys", [])),
        
        "analyzed_at": datetime.now().isoformat()
    }
    
    # Insert snapshot (upsert to handle duplicates)
    result = supabase.table("analysis_snapshots").upsert(
        snapshot_data,
        on_conflict="team_id,run_number"
    ).execute()
    
    return {
        "snapshotId": snapshot_data["id"],
        "teamId": team_id,
        "runNumber": run_number,
        "message": "Snapshot created successfully"
    }


@router.delete("/snapshot/{snapshot_id}", dependencies=[Depends(RoleChecker(["admin"]))])
async def delete_snapshot(
    snapshot_id: str,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Delete a historical snapshot (admin only).
    Use carefully - this removes historical data.
    """
    supabase = get_supabase_admin_client()
    
    result = supabase.table("analysis_snapshots").delete().eq("id", snapshot_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return {"message": "Snapshot deleted successfully"}
