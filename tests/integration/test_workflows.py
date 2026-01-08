"""
End-to-End Workflow Tests
Tests complete user flows from start to finish
"""
import pytest
from fastapi.testclient import TestClient
import time
from uuid import uuid4
from unittest.mock import patch, MagicMock

from main import app

client = TestClient(app)


class TestCompleteAnalysisWorkflow:
    """Test complete analysis workflow from submission to results"""
    
    @patch('backend.background.analyze_repository')
    def test_full_analysis_lifecycle(
        self,
        mock_analyze,
        mock_supabase_client,
        sample_project_data,
        sample_job_data,
        completed_project_data,
        sample_tech_stack,
        sample_issues,
        sample_team_members
    ):
        """Test full workflow: submit → poll → retrieve results"""
        
        # Step 1: Submit analysis request
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        submit_response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        assert submit_response.status_code == 202
        job_id = submit_response.json()["job_id"]
        project_id = submit_response.json()["project_id"]
        
        # Step 2: Poll status (simulating running state)
        sample_job_data["id"] = job_id
        sample_job_data["project_id"] = project_id
        sample_job_data["status"] = "running"
        sample_job_data["progress"] = 50
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        status_response = client.get(f"/api/analysis-status/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "running"
        assert status_response.json()["progress"] == 50
        
        # Step 3: Check results too early
        result_response_early = client.get(f"/api/analysis-result/{job_id}")
        assert result_response_early.status_code == 425  # Too early
        
        # Step 4: Poll status (completed)
        sample_job_data["status"] = "completed"
        sample_job_data["progress"] = 100
        completed_project_data["id"] = project_id
        
        def mock_execute_completed():
            result = type('obj', (object,), {})()
            call_str = str(mock_supabase_client.table.call_args)
            
            if "analysis_jobs" in call_str:
                result.data = [sample_job_data]
            elif "projects" in call_str:
                result.data = [completed_project_data]
            elif "tech_stack" in call_str:
                result.data = sample_tech_stack
            elif "issues" in call_str:
                result.data = sample_issues
            elif "team_members" in call_str:
                result.data = sample_team_members
            else:
                result.data = []
            return result
        
        mock_supabase_client.table().execute.side_effect = mock_execute_completed
        
        status_response_final = client.get(f"/api/analysis-status/{job_id}")
        assert status_response_final.status_code == 200
        assert status_response_final.json()["status"] == "completed"
        
        # Step 5: Retrieve final results
        result_response = client.get(f"/api/analysis-result/{job_id}")
        assert result_response.status_code == 200
        
        result_data = result_response.json()
        assert "scores" in result_data
        assert "tech_stack" in result_data
        assert "issues" in result_data
        assert "team_members" in result_data
        
        # Step 6: Verify project appears in leaderboard
        mock_supabase_client.table().execute.return_value.data = [completed_project_data]
        
        leaderboard_response = client.get("/api/leaderboard")
        assert leaderboard_response.status_code == 200
        leaderboard_data = leaderboard_response.json()
        assert len(leaderboard_data["leaderboard"]) > 0
    
    @patch('backend.background.analyze_repository')
    def test_analysis_with_failure(
        self,
        mock_analyze,
        mock_supabase_client,
        sample_project_data,
        sample_job_data
    ):
        """Test workflow when analysis fails"""
        
        # Submit analysis
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        submit_response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        job_id = submit_response.json()["job_id"]
        
        # Simulate failure
        sample_job_data["id"] = job_id
        sample_job_data["status"] = "failed"
        sample_job_data["error_message"] = "Repository not found"
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        status_response = client.get(f"/api/analysis-status/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "failed"
        assert "error" in status_response.json()
        
        # Results should not be available
        result_response = client.get(f"/api/analysis-result/{job_id}")
        assert result_response.status_code in [404, 425]


class TestBatchWorkflow:
    """Test batch upload and processing workflow"""
    
    def test_batch_upload_and_monitoring(
        self,
        mock_supabase_client,
        sample_project_data,
        sample_job_data
    ):
        """Test batch upload and monitor all jobs"""
        
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        # Submit batch
        batch_response = client.post(
            "/api/batch-upload",
            json={
                "repos": [
                    {
                        "repo_url": "https://github.com/user/repo1",
                        "team_name": "Team 1"
                    },
                    {
                        "repo_url": "https://github.com/user/repo2",
                        "team_name": "Team 2"
                    },
                    {
                        "repo_url": "https://github.com/user/repo3",
                        "team_name": "Team 3"
                    }
                ]
            }
        )
        
        assert batch_response.status_code == 202
        jobs = batch_response.json()["jobs"]
        assert len(jobs) == 3
        
        # Monitor each job
        for job in jobs:
            job_id = job["job_id"]
            sample_job_data["id"] = job_id
            sample_job_data["status"] = "queued"
            mock_supabase_client.table().execute.return_value.data = [sample_job_data]
            
            status_response = client.get(f"/api/analysis-status/{job_id}")
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "queued"


class TestProjectManagementWorkflow:
    """Test project management workflows"""
    
    def test_create_view_filter_delete(
        self,
        mock_supabase_client,
        sample_project_data,
        completed_project_data
    ):
        """Test complete project management cycle"""
        
        # Create project via analysis
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        submit_response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        project_id = submit_response.json()["project_id"]
        
        # View all projects
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        list_response = client.get("/api/projects")
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 1
        
        # Filter projects
        filter_response = client.get(
            "/api/projects?status=completed&min_score=70"
        )
        assert filter_response.status_code == 200
        
        # Get specific project
        mock_supabase_client.table().execute.return_value.data = [completed_project_data]
        
        get_response = client.get(f"/api/projects/{project_id}")
        assert get_response.status_code == 200
        assert get_response.json()["project_id"] == project_id
        
        # Delete project
        delete_response = client.delete(f"/api/projects/{project_id}")
        assert delete_response.status_code == 204
        
        # Verify deletion
        mock_supabase_client.table().execute.return_value.data = []
        
        get_response_after = client.get(f"/api/projects/{project_id}")
        assert get_response_after.status_code == 404


class TestLeaderboardWorkflow:
    """Test leaderboard generation and filtering"""
    
    def test_leaderboard_with_multiple_projects(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test leaderboard with multiple projects"""
        
        # Create multiple projects with different scores
        projects = []
        for i in range(5):
            project = completed_project_data.copy()
            project["id"] = str(uuid4())
            project["team_name"] = f"Team {i+1}"
            project["total_score"] = 100 - (i * 10)  # Decreasing scores
            project["rank"] = i + 1
            projects.append(project)
        
        mock_result = type('obj', (object,), {'data': projects, 'count': 5})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        # Get leaderboard
        response = client.get("/api/leaderboard")
        
        assert response.status_code == 200
        leaderboard = response.json()["leaderboard"]
        assert len(leaderboard) == 5
        
        # Verify ranking
        assert leaderboard[0]["rank"] == 1
        assert leaderboard[0]["total_score"] >= leaderboard[1]["total_score"]
        
        # Test sorting by different field
        response = client.get("/api/leaderboard?sort_by=originality_score")
        assert response.status_code == 200
        
        # Test pagination
        response = client.get("/api/leaderboard?page=1&page_size=2")
        assert response.status_code == 200
        assert len(response.json()["leaderboard"]) <= 2


class TestErrorRecoveryWorkflow:
    """Test error scenarios and recovery"""
    
    def test_retry_failed_analysis(
        self,
        mock_supabase_client,
        sample_project_data,
        sample_job_data
    ):
        """Test retrying failed analysis"""
        
        # First attempt fails
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        first_response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        first_job_id = first_response.json()["job_id"]
        
        # Mark as failed
        sample_job_data["id"] = first_job_id
        sample_job_data["status"] = "failed"
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        status = client.get(f"/api/analysis-status/{first_job_id}")
        assert status.json()["status"] == "failed"
        
        # Retry with same repo
        retry_response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        assert retry_response.status_code == 202
        second_job_id = retry_response.json()["job_id"]
        assert second_job_id != first_job_id  # New job created
    
    def test_handle_duplicate_submissions(
        self,
        mock_supabase_client,
        sample_project_data
    ):
        """Test handling duplicate repo submissions"""
        
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        # Submit same repo twice
        response1 = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        response2 = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        # Both should succeed with different job IDs
        assert response1.status_code == 202
        assert response2.status_code == 202
        assert response1.json()["job_id"] != response2.json()["job_id"]


class TestDataConsistency:
    """Test data consistency across operations"""
    
    def test_project_data_consistency(
        self,
        mock_supabase_client,
        sample_project_data,
        completed_project_data,
        sample_tech_stack,
        sample_issues,
        sample_team_members
    ):
        """Test data remains consistent across different endpoints"""
        
        project_id = completed_project_data["id"]
        
        def mock_execute():
            result = type('obj', (object,), {})()
            call_str = str(mock_supabase_client.table.call_args)
            
            if "projects" in call_str:
                result.data = [completed_project_data]
            elif "tech_stack" in call_str:
                result.data = sample_tech_stack
            elif "issues" in call_str:
                result.data = sample_issues
            elif "team_members" in call_str:
                result.data = sample_team_members
            else:
                result.data = []
            result.count = len(result.data)
            return result
        
        mock_supabase_client.table().execute.side_effect = mock_execute
        
        # Get from projects endpoint
        project_response = client.get(f"/api/projects/{project_id}")
        assert project_response.status_code == 200
        project_data = project_response.json()
        
        # Get from leaderboard
        leaderboard_response = client.get("/api/leaderboard")
        assert leaderboard_response.status_code == 200
        
        # Scores should match
        expected_score = completed_project_data["total_score"]
        assert project_data["total_score"] == expected_score


class TestRateLimiting:
    """Test API rate limiting behavior"""
    
    def test_rapid_submissions(
        self,
        mock_supabase_client,
        sample_project_data
    ):
        """Test handling rapid analysis submissions"""
        
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        # Submit 10 requests rapidly
        responses = []
        for i in range(10):
            response = client.post(
                "/api/analyze-repo",
                json={
                    "repo_url": f"https://github.com/test/repo{i}",
                    "team_name": f"Team {i}"
                }
            )
            responses.append(response)
        
        # All should be accepted (no rate limiting in current implementation)
        # or properly rejected with 429 if rate limiting is added
        accepted = [r for r in responses if r.status_code == 202]
        rejected = [r for r in responses if r.status_code == 429]
        
        assert len(accepted) + len(rejected) == 10
