"""
Integration Tests for API Endpoints
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import json


# Import app after mocking environment
from main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_root_endpoint(self):
        """Test root endpoint returns API info"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data
    
    def test_health_check_when_healthy(self, mock_supabase_client):
        """Test health check with working database"""
        mock_supabase_client.table().execute.return_value.data = []
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


class TestAnalysisEndpoints:
    """Test analysis-related endpoints"""
    
    def test_analyze_repo_success(self, mock_supabase_client, sample_project_data, sample_job_data):
        """Test successful repository analysis request"""
        # Mock responses
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        # Make request
        response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://github.com/test/repo",
                "team_name": "Test Team"
            }
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "project_id" in data
        assert data["status"] == "queued"
    
    def test_analyze_repo_invalid_url(self):
        """Test analysis with invalid URL"""
        response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "not-a-url"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_analyze_repo_non_github_url(self):
        """Test analysis with non-GitHub URL"""
        response = client.post(
            "/api/analyze-repo",
            json={
                "repo_url": "https://gitlab.com/user/repo"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_analyze_repo_missing_url(self):
        """Test analysis without URL"""
        response = client.post(
            "/api/analyze-repo",
            json={}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_analysis_status_success(self, mock_supabase_client, sample_job_data):
        """Test getting analysis status"""
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        job_id = sample_job_data["id"]
        response = client.get(f"/api/analysis-status/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert "progress" in data
    
    def test_get_analysis_status_not_found(self, mock_supabase_client):
        """Test getting status for non-existent job"""
        mock_supabase_client.table().execute.return_value.data = []
        
        job_id = str(uuid4())
        response = client.get(f"/api/analysis-status/{job_id}")
        
        assert response.status_code == 404
    
    def test_get_analysis_status_invalid_uuid(self):
        """Test getting status with invalid UUID"""
        response = client.get("/api/analysis-status/not-a-uuid")
        
        assert response.status_code == 422
    
    def test_get_analysis_result_success(
        self,
        mock_supabase_client,
        sample_job_data,
        completed_project_data,
        sample_tech_stack,
        sample_issues,
        sample_team_members
    ):
        """Test getting completed analysis results"""
        # Setup completed job
        sample_job_data["status"] = "completed"
        sample_job_data["progress"] = 100
        
        # Mock all data
        def mock_execute():
            result = type('obj', (object,), {})()
            if "analysis_jobs" in str(mock_supabase_client.table.call_args):
                result.data = [sample_job_data]
            elif "projects" in str(mock_supabase_client.table.call_args):
                result.data = [completed_project_data]
            elif "tech_stack" in str(mock_supabase_client.table.call_args):
                result.data = sample_tech_stack
            elif "issues" in str(mock_supabase_client.table.call_args):
                result.data = sample_issues
            elif "team_members" in str(mock_supabase_client.table.call_args):
                result.data = sample_team_members
            else:
                result.data = []
            return result
        
        mock_supabase_client.table().execute.side_effect = mock_execute
        
        job_id = sample_job_data["id"]
        response = client.get(f"/api/analysis-result/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        assert "tech_stack" in data
        assert "issues" in data
        assert "team_members" in data
    
    def test_get_analysis_result_not_completed(
        self,
        mock_supabase_client,
        sample_job_data
    ):
        """Test getting results for incomplete analysis"""
        sample_job_data["status"] = "running"
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        job_id = sample_job_data["id"]
        response = client.get(f"/api/analysis-result/{job_id}")
        
        assert response.status_code == 425  # Too Early


class TestProjectsEndpoints:
    """Test project management endpoints"""
    
    def test_list_projects_default(self, mock_supabase_client, sample_project_data):
        """Test listing projects with defaults"""
        mock_result = type('obj', (object,), {'data': [sample_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        response = client.get("/api/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total" in data
        assert "page" in data
        assert data["total"] == 1
    
    def test_list_projects_with_filters(self, mock_supabase_client, completed_project_data):
        """Test listing projects with filters"""
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        response = client.get(
            "/api/projects?status=completed&min_score=70&max_score=90&page=1&page_size=10"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["projects"]) == 1
    
    def test_list_projects_invalid_page(self):
        """Test listing with invalid page number"""
        response = client.get("/api/projects?page=0")
        
        assert response.status_code == 422
    
    def test_list_projects_invalid_score_range(self):
        """Test listing with invalid score range"""
        response = client.get("/api/projects?min_score=150")
        
        assert response.status_code == 422
    
    def test_get_project_by_id(self, mock_supabase_client, completed_project_data):
        """Test getting single project"""
        mock_supabase_client.table().execute.return_value.data = [completed_project_data]
        
        project_id = completed_project_data["id"]
        response = client.get(f"/api/projects/{project_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == project_id
    
    def test_get_project_not_found(self, mock_supabase_client):
        """Test getting non-existent project"""
        mock_supabase_client.table().execute.return_value.data = []
        
        project_id = str(uuid4())
        response = client.get(f"/api/projects/{project_id}")
        
        assert response.status_code == 404
    
    def test_delete_project_success(self, mock_supabase_client, sample_project_data):
        """Test deleting project"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        project_id = sample_project_data["id"]
        response = client.delete(f"/api/projects/{project_id}")
        
        assert response.status_code == 204
    
    def test_delete_project_not_found(self, mock_supabase_client):
        """Test deleting non-existent project"""
        mock_supabase_client.table().execute.return_value.data = []
        
        project_id = str(uuid4())
        response = client.delete(f"/api/projects/{project_id}")
        
        assert response.status_code == 404


class TestLeaderboardEndpoints:
    """Test leaderboard endpoints"""
    
    def test_get_leaderboard_default(self, mock_supabase_client, completed_project_data):
        """Test leaderboard with defaults"""
        completed_project_data["rank"] = 1
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        response = client.get("/api/leaderboard")
        
        assert response.status_code == 200
        data = response.json()
        assert "leaderboard" in data
        assert len(data["leaderboard"]) == 1
        assert data["leaderboard"][0]["rank"] == 1
    
    def test_get_leaderboard_custom_sort(self, mock_supabase_client, completed_project_data):
        """Test leaderboard with custom sorting"""
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        response = client.get(
            "/api/leaderboard?sort_by=originality_score&order=desc"
        )
        
        assert response.status_code == 200
    
    def test_get_leaderboard_invalid_sort_field(self, mock_supabase_client):
        """Test leaderboard with invalid sort field"""
        response = client.get("/api/leaderboard?sort_by=invalid_field")
        
        assert response.status_code == 400
    
    def test_get_leaderboard_invalid_order(self, mock_supabase_client):
        """Test leaderboard with invalid order"""
        response = client.get("/api/leaderboard?order=invalid")
        
        assert response.status_code == 400
    
    def test_batch_upload_success(self, mock_supabase_client, sample_project_data, sample_job_data):
        """Test batch upload"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        response = client.post(
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
                    }
                ]
            }
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "jobs" in data
        assert "total" in data
    
    def test_batch_upload_empty_list(self):
        """Test batch upload with empty list"""
        response = client.post(
            "/api/batch-upload",
            json={"repos": []}
        )
        
        assert response.status_code == 422
    
    def test_batch_upload_too_many(self):
        """Test batch upload with too many repos"""
        repos = [
            {"repo_url": f"https://github.com/user/repo{i}"}
            for i in range(51)
        ]
        
        response = client.post(
            "/api/batch-upload",
            json={"repos": repos}
        )
        
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_json_request(self):
        """Test request with invalid JSON"""
        response = client.post(
            "/api/analyze-repo",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
    
    def test_missing_required_fields(self):
        """Test request with missing required fields"""
        response = client.post(
            "/api/analyze-repo",
            json={"team_name": "Test"}  # Missing repo_url
        )
        
        assert response.status_code == 422
    
    def test_invalid_uuid_format(self):
        """Test endpoints with invalid UUID format"""
        response = client.get("/api/analysis-status/not-a-uuid")
        assert response.status_code == 422
        
        response = client.get("/api/projects/not-a-uuid")
        assert response.status_code == 422
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.options(
            "/api/projects",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Check CORS headers
        assert "access-control-allow-origin" in response.headers


class TestConcurrency:
    """Test concurrent request handling"""
    
    def test_multiple_analyze_requests(self, mock_supabase_client, sample_project_data):
        """Test multiple simultaneous analysis requests"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        responses = []
        for i in range(5):
            response = client.post(
                "/api/analyze-repo",
                json={
                    "repo_url": f"https://github.com/test/repo{i}",
                    "team_name": f"Team {i}"
                }
            )
            responses.append(response)
        
        # All should succeed
        assert all(r.status_code == 202 for r in responses)
        
        # All should have unique job IDs
        job_ids = [r.json()["job_id"] for r in responses]
        assert len(set(job_ids)) == 5
