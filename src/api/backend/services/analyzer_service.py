"""
Analyzer Service
Wrapper for agent.py pipeline with progress tracking
"""
import os
import sys
from uuid import UUID
from typing import Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.agent import build_pipeline
from src.api.backend.utils.progress_tracker import ProgressTracker
from src.api.backend.services.data_mapper import DataMapper
from src.api.backend.crud import TeamCRUD
from src.utils.git_utils import cleanup_repo



class AnalyzerService:
    """Service to run repository analysis with progress tracking"""

    @staticmethod
    def _fetch_github_languages(repo_url: str, token: str) -> Dict[str, float]:
        """Fetch language breakdown from GitHub API"""
        import httpx
        
        try:
            # Extract owner/repo
            cleaned = repo_url.rstrip("/").replace(".git", "")
            parts = cleaned.split("/")
            if len(parts) < 2:
                return {}
            repo_path = f"{parts[-2]}/{parts[-1]}"
            
            api_url = f"https://api.github.com/repos/{repo_path}/languages"
            
            with httpx.Client() as client:
                response = client.get(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github.v3+json"
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    print(f"      ⚠️  GitHub API Lookup Failed: {response.status_code}")
                    return {}
                
                data = response.json()
                total_bytes = sum(data.values())
                
                if total_bytes == 0:
                    return {}
                    
                breakdown = {}
                for lang, bytes_count in data.items():
                    percentage = round((bytes_count / total_bytes) * 100, 2)
                    breakdown[lang] = percentage
                    
                return breakdown
                
        except Exception as e:
            print(f"      ⚠️  Language fetch error: {e}")
            return {}

    
    @staticmethod
    def analyze_repository(team_id: UUID, job_id: UUID, repo_url: str, team_name: str = None) -> Dict[str, Any]:
        """
        Run full analysis pipeline on a repository
        
        Args:
            team_id: UUID of the team (parameter renamed from project_id for clarity)
            job_id: UUID of the analysis job
            repo_url: GitHub repository URL
            team_name: Optional team name
            
        Returns:
            Analysis report dictionary
        """
        tracker = ProgressTracker(job_id)
        repo_path = None
        
        try:
            # Update team status
            TeamCRUD.update_team_status(team_id, "analyzing")
            tracker.update("starting")
            
            # Prepare output directory
            output_dir = f"reports/{team_name or str(team_id)}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Get API keys from environment
            gemini_key = os.getenv("GEMINI_API_KEY")
            
            # LLM providers for forensics (currently disabled by default)
            providers = []  # Can be populated from config if needed
            
            print(f"\n{'='*60}")
            print(f"🚀 Starting Analysis: {repo_url}")
            print(f"{'='*60}\n")
            
            # Create progress callback function
            def progress_callback(stage: str, progress: int):
                """Callback to update progress during analysis"""
                tracker.update(stage, progress)
            
            # Build and run the pipeline with progress tracking
            final_report = build_pipeline(
                repo_url=repo_url,
                output_dir=output_dir,
                providers=providers,
                gemini_key=gemini_key,
                progress_callback=progress_callback
            )
            
            # Extract report
            if final_report and "final_report" in final_report:
                report = final_report["final_report"]
            else:
                report = final_report
            
            # Get repo_path for cleanup
            if report and "repo" in report:
                # Extract repo path if available
                pass

            # Fetch languages from GitHub API
            # Fetch languages from GitHub API
            gh_token = os.getenv("GH_API_KEY") or os.getenv("GITHUB_TOKEN")
            if gh_token and repo_url:
                try:
                    languages = AnalyzerService._fetch_github_languages(repo_url, gh_token)
                    if languages:
                        print(f"      📝 Fetched language data: {list(languages.keys())}")
                        if "final_report" in final_report:
                            final_report["final_report"]["languages"] = languages
                        else:
                            final_report["languages"] = languages
                        report = final_report if "final_report" not in final_report else final_report["final_report"]
                except Exception as e:
                    print(f"      ⚠️  Failed to fetch languages: {e}")
            
            # Save results to database
            tracker.update("aggregation", 95)
            success = DataMapper.save_analysis_results(team_id, report)
            
            if not success:
                raise Exception("Failed to save analysis results to database")
            
            # Mark job as completed
            tracker.complete()
            
            print(f"\n{'='*60}")
            print(f"✅ Analysis Complete!")
            print(f"{'='*60}\n")
            
            return report
            
        except Exception as e:
            # Mark job as failed
            error_msg = str(e)
            print(f"\n{'='*60}")
            print(f"❌ Analysis Failed: {error_msg}")
            print(f"{'='*60}\n")
            
            tracker.fail(error_msg)
            TeamCRUD.update_team_status(team_id, "failed")
            
            raise
        
        finally:
            # Cleanup cloned repository if it exists
            if repo_path and os.path.exists(repo_path):
                try:
                    cleanup_repo(repo_path)
                except Exception as e:
                    print(f"      ⚠️  Failed to cleanup repo: {e}")
