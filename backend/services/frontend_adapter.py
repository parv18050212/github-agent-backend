"""
Frontend Adapter Service
Transforms backend data to match frontend expectations
"""
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime


class FrontendAdapter:
    """Adapts backend responses to frontend format"""
    
    @staticmethod
    def transform_project_response(project_data: Dict[str, Any], 
                                   tech_stack: List[Dict], 
                                   issues: List[Dict],
                                   team_members: List[Dict],
                                   report_json: Dict[str, Any] = None) -> Dict[str, Any]:
        """Transform to frontend ProjectEvaluation format"""
        
        # Extract languages from report or tech stack
        languages = []
        if report_json and "languages" in report_json:
            lang_data = report_json.get("languages", {})
            for lang, pct in lang_data.items():
                languages.append({"name": lang, "percentage": pct})
        
        # Extract tech stack names
        tech_names = [t.get("technology") for t in tech_stack if t.get("technology")]
        
        # Extract frameworks
        frameworks = [t.get("technology") for t in tech_stack 
                     if t.get("category") == "framework"]
        
        # Transform contributors
        contributors = []
        for member in team_members:
            contributors.append({
                "name": member.get("name"),
                "commits": member.get("commits", 0),
                "additions": 0,  # Not tracked yet
                "deletions": 0,  # Not tracked yet
                "percentage": member.get("contribution_pct", 0)
            })
        
        # Transform security issues
        security_issues = []
        secrets_count = 0
        for issue in issues:
            if issue.get("type") == "security":
                secrets_count += 1
                security_issues.append({
                    "type": "Hardcoded Secret" if "secret" in issue.get("description", "").lower() else "Security Issue",
                    "severity": issue.get("severity", "medium"),
                    "file": issue.get("file_path", "Unknown"),
                    "line": None,
                    "description": issue.get("description", "")
                })
        
        # Calculate AI percentage
        ai_percentage = 0.0
        if report_json and "files" in report_json:
            files = report_json.get("files", [])
            if files:
                total_ai = sum(f.get("ai_pct", 0) for f in files)
                ai_percentage = round(total_ai / len(files), 2)
        
        # Extract verdict details
        ai_verdict = None
        strengths = []
        improvements = []
        
        if report_json and "judge" in report_json:
            judge = report_json.get("judge", {})
            ai_verdict = f"{judge.get('positive_feedback', '')}\\n\\n{judge.get('constructive_feedback', '')}"
            
            # Parse strengths and improvements
            pos_feedback = judge.get("positive_feedback", "")
            if pos_feedback:
                strengths = [s.strip() for s in pos_feedback.split(".") if s.strip()]
            
            const_feedback = judge.get("constructive_feedback", "")
            if const_feedback:
                improvements = [s.strip() for s in const_feedback.split(".") if s.strip()]
        
        # Calculate total files and LOC
        total_files = 0
        total_loc = 0
        if report_json:
            files = report_json.get("files", [])
            total_files = len(files)
            # Estimate LOC (not directly tracked)
            total_loc = total_files * 100  # Rough estimate
        
        return {
            # Identity
            "id": project_data.get("id"),
            "teamName": project_data.get("team_name"),
            "repoUrl": project_data.get("repo_url"),
            "submittedAt": project_data.get("created_at"),
            "status": project_data.get("status", "completed"),
            
            # Tech Stack
            "techStack": tech_names,
            "languages": languages,
            "architecturePattern": report_json.get("architecture", "Monolithic") if report_json else "Monolithic",
            "frameworks": frameworks,
            
            # Scores
            "totalScore": project_data.get("total_score", 0),
            "qualityScore": project_data.get("quality_score", 0),
            "securityScore": project_data.get("security_score", 0),
            "originalityScore": project_data.get("originality_score", 0),
            "architectureScore": project_data.get("engineering_score", 0),
            "documentationScore": project_data.get("documentation_score", 0),
            
            # Commit Forensics
            "totalCommits": project_data.get("total_commits", 0),
            "contributors": contributors,
            "commitPatterns": [],  # Would need git log analysis
            "burstCommitWarning": False,  # Would need commit timing analysis
            "lastMinuteCommits": 0,  # Would need deadline tracking
            
            # Security
            "securityIssues": security_issues,
            "secretsDetected": secrets_count,
            
            # AI Analysis
            "aiGeneratedPercentage": ai_percentage,
            "aiVerdict": ai_verdict,
            "strengths": strengths[:5] if strengths else [],
            "improvements": improvements[:5] if improvements else [],
            
            # Project Stats
            "totalFiles": total_files,
            "totalLinesOfCode": total_loc,
            "testCoverage": 0  # Not tracked yet
        }
    
    @staticmethod
    def transform_project_list_item(project: Dict[str, Any], tech_stack: List[Dict] = None) -> Dict[str, Any]:
        """Transform for project list/dashboard"""
        tech_names = []
        if tech_stack:
            tech_names = [t.get("technology") for t in tech_stack if t.get("technology")]
        
        return {
            "id": project.get("id"),
            "teamName": project.get("team_name"),
            "repoUrl": project.get("repo_url"),
            "status": project.get("status"),
            "totalScore": project.get("total_score", 0),
            "techStack": tech_names[:5],  # Top 5
            "securityIssues": 0,  # Would need to query issues table
            "submittedAt": project.get("created_at")
        }
    
    @staticmethod
    def transform_leaderboard_item(project: Dict[str, Any]) -> Dict[str, Any]:
        """Transform for leaderboard"""
        return {
            "id": project.get("id"),
            "teamName": project.get("team_name"),
            "repoUrl": project.get("repo_url"),
            "techStack": [],  # Would need to join tech_stack table
            "totalScore": project.get("total_score", 0),
            "qualityScore": project.get("quality_score", 0),
            "securityScore": project.get("security_score", 0),
            "originalityScore": project.get("originality_score", 0),
            "architectureScore": project.get("engineering_score", 0),
            "documentationScore": project.get("documentation_score", 0)
        }
