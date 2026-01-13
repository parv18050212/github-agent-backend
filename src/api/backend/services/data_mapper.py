"""
Data Mapper Service
Maps agent.py output to Supabase database format
"""
from typing import Dict, Any, List
from uuid import UUID
from datetime import datetime
from src.api.backend.crud import ProjectCRUD, TechStackCRUD, IssueCRUD, TeamMemberCRUD
from src.api.backend.utils.cache import cache
from src.api.backend.utils.logger import batch_logger


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
        import traceback
        
        try:
            # 1. Update project with scores
            scores = DataMapper.map_scores(report)
            
            judge = report.get("judge", {}) or {}
            verdict = judge.get("verdict", "Unknown")
            ai_pros = judge.get("positive_feedback", "")
            ai_cons = judge.get("constructive_feedback", "")
            
            # Map to actual database column names (user's schema)
            project_data = {
                **scores,
                "total_commits": report.get("total_commits", 0),
                "verdict": str(verdict)[:255] if verdict else None,
                "ai_pros": str(ai_pros)[:5000] if ai_pros else None,
                "ai_cons": str(ai_cons)[:5000] if ai_cons else None,
                "status": "completed",
                "analyzed_at": datetime.now().isoformat()
            }
            
            # Try to add report_json (may fail if too large or invalid)
            try:
                # Get full commit details with all commits
                commit_details = report.get("commit_details", {})
                
                report_json = {
                    "scores": report.get("scores", {}),
                    "stack": report.get("stack", []),
                    "files": report.get("files", [])[:30],  # Limit to avoid size issues
                    "judge": judge,
                    "team": report.get("team", {}),
                    "security": report.get("security", {}),
                    "maturity": report.get("maturity", {}),
                    "structure": report.get("structure", {}),
                    "repo_tree": report.get("repo_tree", ""),  # Add repository tree structure
                    "total_commits": report.get("total_commits", 0),
                    "commit_details": commit_details,  # Include full commit details with all_commits
                    "forensics": {
                        "author_stats": report.get("team", {}),
                        "total_commits": report.get("total_commits", 0)
                    }
                }
                project_data["report_json"] = report_json
            except Exception as json_err:
                batch_logger.warning(f"Could not build report_json: {json_err}")
            
            # Try saving with report_json first
            batch_logger.info(f"Saving project data for {project_id}...")
            try:
                ProjectCRUD.update_project(project_id, project_data)
                batch_logger.info(f"Project data saved successfully")
            except Exception as save_err:
                batch_logger.warning(f"Save with report_json failed: {save_err}")
                # Retry without report_json
                if "report_json" in project_data:
                    del project_data["report_json"]
                batch_logger.info(f"Retrying without report_json...")
                ProjectCRUD.update_project(project_id, project_data)
                batch_logger.info(f"Project data saved (without report_json)")
            
            # 2. Save tech stack
            try:
                tech_stack = DataMapper.map_tech_stack(report)
                if tech_stack:
                    batch_logger.info(f"Saving {len(tech_stack)} tech stack items...")
                    TechStackCRUD.add_technologies(project_id, tech_stack)
            except Exception as e:
                batch_logger.error(f"Failed to save tech stack: {e}")
            
            # 3. Save issues  
            try:
                issues = DataMapper.map_issues(report, project_id)
                if issues:
                    batch_logger.info(f"Saving {len(issues)} issues...")
                    IssueCRUD.add_issues(project_id, issues)
            except Exception as e:
                batch_logger.error(f"Failed to save issues: {e}")
            
            # 4. Save team members
            try:
                team_members = DataMapper.map_team_members(report)
                if team_members:
                    batch_logger.info(f"Saving {len(team_members)} team members...")
                    TeamMemberCRUD.add_members(project_id, team_members)
            except Exception as e:
                batch_logger.error(f"Failed to save team members: {e}")
            
            # 5. Invalidate cache for this project
            try:
                cache.invalidate_project(str(project_id))
                batch_logger.info(f"Cache invalidated for project {project_id}")
            except Exception as e:
                batch_logger.warning(f"Failed to invalidate cache: {e}")
            
            return True
            
        except Exception as e:
            batch_logger.error(f"Error saving results: {e}")
            batch_logger.error(f"Traceback: {traceback.format_exc()}")
            return False
