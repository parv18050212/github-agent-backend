"""
Data Mapper Service
Maps agent.py output to Supabase database format
"""
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime
from backend.crud import ProjectCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD


class DataMapper:
    """Map analysis results to database format"""
    
    @staticmethod
    def calculate_total_score(scores: Dict[str, float]) -> float:
        """Calculate weighted total score"""
        weights = {
            "originality": 0.20,
            "quality": 0.15,
            "security": 0.10,
            "effort": 0.10,
            "implementation": 0.25,
            "engineering": 0.10,
            "organization": 0.05,
            "documentation": 0.05
        }
        
        total = 0.0
        for key, weight in weights.items():
            score = scores.get(f"{key}_score", 0) or 0
            total += score * weight
        
        return round(total, 2)
    
    @staticmethod
    def map_scores(report: Dict[str, Any]) -> Dict[str, float]:
        """Extract and map scores from report"""
        scores = report.get("scores", {})
        
        mapped_scores = {
            "originality_score": scores.get("originality", 0),
            "quality_score": scores.get("quality", 0),
            "security_score": scores.get("security", 0),
            "effort_score": scores.get("effort", 0),
            "implementation_score": scores.get("implementation", 0),
            "engineering_score": scores.get("engineering", 0),
            "organization_score": scores.get("organization", 0),
            "documentation_score": scores.get("documentation", 0)
        }
        
        # Calculate total score
        mapped_scores["total_score"] = DataMapper.calculate_total_score(mapped_scores)
        
        return mapped_scores
    
    @staticmethod
    def map_tech_stack(report: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract tech stack from report"""
        stack = report.get("stack", [])
        
        if isinstance(stack, str):
            # If stack is a comma-separated string
            stack = [s.strip() for s in stack.split(",")]
        
        technologies = []
        for tech in stack:
            if not tech:
                continue
            
            # Try to categorize
            tech_lower = tech.lower()
            category = None
            
            if any(lang in tech_lower for lang in ["python", "javascript", "java", "typescript", "go", "rust", "cpp", "c++"]):
                category = "language"
            elif any(fw in tech_lower for fw in ["react", "vue", "angular", "django", "flask", "fastapi", "express", "next"]):
                category = "framework"
            elif any(db in tech_lower for db in ["postgres", "mysql", "mongo", "redis", "sqlite", "supabase"]):
                category = "database"
            else:
                category = "tool"
            
            technologies.append({
                "technology": tech,
                "category": category
            })
        
        return technologies
    
    @staticmethod
    def map_issues(report: Dict[str, Any], project_id: UUID) -> List[Dict[str, Any]]:
        """Extract issues from report"""
        issues = []
        
        # Security issues
        security = report.get("security", {})
        if security.get("leaked_keys"):
            for leak in security.get("leaked_keys", []):
                issues.append({
                    "type": "security",
                    "severity": "high",
                    "file_path": leak.get("file"),
                    "description": f"Secret detected: {leak.get('type', 'Unknown')}",
                    "ai_probability": None,
                    "plagiarism_score": None
                })
        
        # AI-generated code issues
        files = report.get("files", [])
        for file_info in files:
            ai_pct = file_info.get("ai_pct", 0)
            plag_pct = file_info.get("plag_pct", 0)
            
            if ai_pct > 50:  # More than 50% AI-generated
                issues.append({
                    "type": "plagiarism",
                    "severity": "high" if ai_pct > 80 else "medium",
                    "file_path": file_info.get("name"),
                    "description": f"High AI-generated probability detected",
                    "ai_probability": ai_pct / 100,
                    "plagiarism_score": None
                })
            
            if plag_pct > 50:  # More than 50% plagiarized
                match = file_info.get("match", "")
                issues.append({
                    "type": "plagiarism",
                    "severity": "high" if plag_pct > 80 else "medium",
                    "file_path": file_info.get("name"),
                    "description": f"High similarity with: {match}",
                    "ai_probability": None,
                    "plagiarism_score": plag_pct / 100
                })
        
        # Quality issues (low maintainability)
        quality = report.get("quality_metrics", {})
        mi = quality.get("maintainability_index", 100)
        if mi < 50:
            issues.append({
                "type": "quality",
                "severity": "medium" if mi > 20 else "high",
                "file_path": None,
                "description": f"Low maintainability index: {mi:.1f}",
                "ai_probability": None,
                "plagiarism_score": None
            })
        
        return issues
    
    @staticmethod
    def map_team_members(report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract team members from report"""
        team = report.get("team", {})
        members = []
        
        if isinstance(team, dict):
            # Team is author_stats dict
            for author, stats in team.items():
                commits = stats if isinstance(stats, int) else stats.get("commits", 0)
                members.append({
                    "name": author,
                    "commits": commits,
                    "contribution_pct": None  # Will be calculated if needed
                })
        
        # Calculate contribution percentages
        total_commits = sum(m["commits"] for m in members)
        if total_commits > 0:
            for member in members:
                member["contribution_pct"] = round((member["commits"] / total_commits) * 100, 2)
        
        return members
    
    @staticmethod
    def save_analysis_results(project_id: UUID, report: Dict[str, Any]) -> bool:
        """Save complete analysis results to database"""
        try:
            # 1. Update project with scores
            scores = DataMapper.map_scores(report)
            
            judge = report.get("judge", {})
            verdict = judge.get("verdict", "Unknown")
            
            # Map to actual database column names (user's schema)
            project_data = {
                **scores,
                "total_commits": report.get("total_commits", 0),
                "verdict": verdict,
                "status": "completed",
                "analyzed_at": datetime.now().isoformat()
                # Note: report_path and viz_path not set here, would need file storage
            }
            
            ProjectCRUD.update_project(project_id, project_data)
            
            # 2. Save tech stack
            tech_stack = DataMapper.map_tech_stack(report)
            if tech_stack:
                TechStackCRUD.add_technologies(project_id, tech_stack)
            
            # 3. Save issues
            issues = DataMapper.map_issues(report, project_id)
            if issues:
                IssueCRUD.add_issues(project_id, issues)
            
            # 4. Save team members
            team_members = DataMapper.map_team_members(report)
            if team_members:
                TeamMemberCRUD.add_members(project_id, team_members)
            
            return True
            
        except Exception as e:
            print(f"      ❌ Error saving results: {e}")
            return False
