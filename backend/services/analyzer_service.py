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

from agent import build_pipeline
from backend.utils.progress_tracker import ProgressTracker
from backend.services.data_mapper import DataMapper
from backend.crud import ProjectCRUD
from utils.git_utils import cleanup_repo


class AnalyzerService:
    """Service to run repository analysis with progress tracking"""
    
    @staticmethod
    def analyze_repository(project_id: UUID, job_id: UUID, repo_url: str, team_name: str = None) -> Dict[str, Any]:
        """
        Run full analysis pipeline on a repository
        
        Args:
            project_id: UUID of the project
            job_id: UUID of the analysis job
            repo_url: GitHub repository URL
            team_name: Optional team name
            
        Returns:
            Analysis report dictionary
        """
        tracker = ProgressTracker(job_id)
        repo_path = None
        
        try:
            # Update project status
            ProjectCRUD.update_project_status(project_id, "analyzing")
            tracker.update("starting")
            
            # Prepare output directory
            output_dir = f"report/{team_name or str(project_id)}"
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
            
            # Save results to database
            tracker.update("aggregation", 95)
            success = DataMapper.save_analysis_results(project_id, report)
            
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
            ProjectCRUD.update_project_status(project_id, "failed")
            
            raise
        
        finally:
            # Cleanup cloned repository if it exists
            if repo_path and os.path.exists(repo_path):
                try:
                    cleanup_repo(repo_path)
                except Exception as e:
                    print(f"      ⚠️  Failed to cleanup repo: {e}")
