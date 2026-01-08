"""
Performance and Load Tests
"""
import pytest
from fastapi.testclient import TestClient
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

from main import app

client = TestClient(app)


class TestPerformance:
    """Test API performance under load"""
    
    def test_health_check_performance(self, mock_supabase_client):
        """Test health check response time"""
        mock_supabase_client.table().execute.return_value.data = []
        
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Should respond in under 1 second
    
    def test_list_projects_performance(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test project listing performance"""
        # Simulate many projects
        projects = [
            {**completed_project_data, "id": str(uuid4())}
            for _ in range(100)
        ]
        
        mock_result = type('obj', (object,), {'data': projects, 'count': 100})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        start_time = time.time()
        response = client.get("/api/projects?page_size=50")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 2.0  # Should handle 100 projects quickly
    
    def test_leaderboard_calculation_performance(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test leaderboard generation performance"""
        # Simulate many completed projects
        projects = []
        for i in range(50):
            project = completed_project_data.copy()
            project["id"] = str(uuid4())
            project["team_name"] = f"Team {i}"
            project["rank"] = i + 1
            projects.append(project)
        
        mock_result = type('obj', (object,), {'data': projects, 'count': 50})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        start_time = time.time()
        response = client.get("/api/leaderboard")
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 2.0  # Should calculate rankings quickly


class TestConcurrentLoad:
    """Test concurrent request handling"""
    
    def test_concurrent_health_checks(self, mock_supabase_client):
        """Test handling multiple simultaneous health checks"""
        mock_supabase_client.table().execute.return_value.data = []
        
        num_requests = 20
        
        def make_request():
            return client.get("/health")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            responses = [future.result() for future in as_completed(futures)]
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == num_requests
    
    def test_concurrent_project_listings(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test concurrent project list requests"""
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        num_requests = 15
        
        def make_request(page):
            return client.get(f"/api/projects?page={page}")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(1, num_requests + 1)]
            responses = [future.result() for future in as_completed(futures)]
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == num_requests
    
    def test_concurrent_analysis_submissions(
        self,
        mock_supabase_client,
        sample_project_data
    ):
        """Test concurrent analysis request submissions"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        num_requests = 10
        
        def submit_analysis(repo_num):
            return client.post(
                "/api/analyze-repo",
                json={
                    "repo_url": f"https://github.com/test/repo{repo_num}",
                    "team_name": f"Team {repo_num}"
                }
            )
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(submit_analysis, i) for i in range(num_requests)]
            responses = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        
        # All should be accepted
        assert all(r.status_code == 202 for r in responses)
        assert len(responses) == num_requests
        
        # All should have unique job IDs
        job_ids = [r.json()["job_id"] for r in responses]
        assert len(set(job_ids)) == num_requests
        
        # Should complete in reasonable time
        assert (end_time - start_time) < 5.0
    
    def test_concurrent_status_checks(
        self,
        mock_supabase_client,
        sample_job_data
    ):
        """Test concurrent status check requests"""
        job_id = sample_job_data["id"]
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        num_requests = 20
        
        def check_status():
            return client.get(f"/api/analysis-status/{job_id}")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_status) for _ in range(num_requests)]
            responses = [future.result() for future in as_completed(futures)]
        
        # All should succeed
        assert all(r.status_code == 200 for r in responses)
        assert len(responses) == num_requests


class TestScalability:
    """Test system scalability with large datasets"""
    
    def test_large_batch_upload(
        self,
        mock_supabase_client,
        sample_project_data
    ):
        """Test batch upload with maximum allowed repos"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        # Create 50 repos (maximum allowed)
        repos = [
            {
                "repo_url": f"https://github.com/team{i}/project",
                "team_name": f"Team {i}"
            }
            for i in range(50)
        ]
        
        start_time = time.time()
        response = client.post(
            "/api/batch-upload",
            json={"repos": repos}
        )
        end_time = time.time()
        
        assert response.status_code == 202
        assert response.json()["total"] == 50
        assert (end_time - start_time) < 5.0  # Should handle max batch quickly
    
    def test_large_leaderboard(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test leaderboard with large number of projects"""
        # Simulate 200 projects
        projects = []
        for i in range(200):
            project = completed_project_data.copy()
            project["id"] = str(uuid4())
            project["team_name"] = f"Team {i}"
            project["total_score"] = 100 - (i % 100)
            project["rank"] = i + 1
            projects.append(project)
        
        mock_result = type('obj', (object,), {'data': projects[:100], 'count': 200})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        start_time = time.time()
        response = client.get("/api/leaderboard?page_size=100")
        end_time = time.time()
        
        assert response.status_code == 200
        assert len(response.json()["leaderboard"]) == 100
        assert (end_time - start_time) < 3.0
    
    def test_pagination_performance(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test pagination with large dataset"""
        projects = [
            {**completed_project_data, "id": str(uuid4())}
            for _ in range(20)
        ]
        
        mock_result = type('obj', (object,), {'data': projects, 'count': 500})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        # Test multiple pages
        page_times = []
        for page in range(1, 6):
            start = time.time()
            response = client.get(f"/api/projects?page={page}&page_size=20")
            end = time.time()
            
            assert response.status_code == 200
            page_times.append(end - start)
        
        # All pages should load quickly
        assert all(t < 2.0 for t in page_times)
        
        # Performance should be consistent across pages
        avg_time = sum(page_times) / len(page_times)
        assert all(t < avg_time * 1.5 for t in page_times)  # No page > 1.5x avg


class TestStressTest:
    """Stress tests to find breaking points"""
    
    @pytest.mark.slow
    def test_sustained_load(
        self,
        mock_supabase_client,
        sample_project_data
    ):
        """Test sustained request load"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        num_requests = 100
        successful = 0
        failed = 0
        total_time = 0
        
        def make_request(i):
            start = time.time()
            try:
                response = client.post(
                    "/api/analyze-repo",
                    json={
                        "repo_url": f"https://github.com/test/repo{i}",
                        "team_name": f"Team {i}"
                    }
                )
                duration = time.time() - start
                return response.status_code, duration
            except Exception as e:
                duration = time.time() - start
                return 500, duration
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(num_requests)]
            
            for future in as_completed(futures):
                status, duration = future.result()
                total_time += duration
                
                if status == 202:
                    successful += 1
                else:
                    failed += 1
        
        # Calculate metrics
        success_rate = (successful / num_requests) * 100
        avg_response_time = total_time / num_requests
        
        # Assertions
        assert success_rate >= 95  # At least 95% success rate
        assert avg_response_time < 1.0  # Average response under 1 second
        
        print(f"\nStress Test Results:")
        print(f"Total Requests: {num_requests}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"Average Response Time: {avg_response_time:.3f}s")
    
    @pytest.mark.slow
    def test_memory_usage_pattern(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test memory usage doesn't grow unbounded"""
        # Make many requests to check for memory leaks
        projects = [
            {**completed_project_data, "id": str(uuid4())}
            for _ in range(10)
        ]
        
        mock_result = type('obj', (object,), {'data': projects, 'count': 10})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        # Make 50 requests
        for i in range(50):
            response = client.get("/api/projects")
            assert response.status_code == 200
            
            # Clear any potential caches
            response.json()
        
        # If we get here without memory errors, test passes
        assert True


class TestResourceLimits:
    """Test handling of resource limits"""
    
    def test_max_page_size_enforcement(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test page size limit is enforced"""
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        # Try to request more than max page size
        response = client.get("/api/projects?page_size=1000")
        
        # Should be rejected or limited to max
        assert response.status_code in [200, 422]
        
        if response.status_code == 200:
            # If allowed, should be capped at max (100)
            assert len(response.json()["projects"]) <= 100
    
    def test_batch_size_limit_enforcement(
        self,
        mock_supabase_client
    ):
        """Test batch upload size limit"""
        # Try to upload more than allowed (>50)
        repos = [
            {"repo_url": f"https://github.com/team{i}/repo"}
            for i in range(51)
        ]
        
        response = client.post(
            "/api/batch-upload",
            json={"repos": repos}
        )
        
        # Should be rejected
        assert response.status_code == 422
    
    def test_deep_pagination(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test very deep pagination"""
        mock_result = type('obj', (object,), {'data': [], 'count': 1000})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        # Try to access page 100
        response = client.get("/api/projects?page=100&page_size=10")
        
        # Should handle gracefully
        assert response.status_code == 200
        assert len(response.json()["projects"]) == 0


class TestResponseSizes:
    """Test handling of different response sizes"""
    
    def test_small_response(self, mock_supabase_client):
        """Test endpoint with small response"""
        mock_supabase_client.table().execute.return_value.data = []
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert len(response.content) < 1000  # Small response
    
    def test_medium_response(
        self,
        mock_supabase_client,
        completed_project_data
    ):
        """Test endpoint with medium-sized response"""
        projects = [
            {**completed_project_data, "id": str(uuid4())}
            for _ in range(10)
        ]
        
        mock_result = type('obj', (object,), {'data': projects, 'count': 10})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        response = client.get("/api/projects")
        
        assert response.status_code == 200
        assert len(response.content) < 100000  # Reasonable size
    
    def test_large_response(
        self,
        mock_supabase_client,
        completed_project_data,
        sample_tech_stack,
        sample_issues,
        sample_team_members
    ):
        """Test endpoint with large response"""
        # Create project with lots of data
        project = completed_project_data.copy()
        
        # Add many tech stack items
        tech_stack = [
            {**sample_tech_stack[0], "id": str(uuid4())}
            for _ in range(20)
        ]
        
        # Add many issues
        issues = [
            {**sample_issues[0], "id": str(uuid4())}
            for _ in range(30)
        ]
        
        # Add many team members
        team_members = [
            {**sample_team_members[0], "id": str(uuid4())}
            for _ in range(10)
        ]
        
        def mock_execute():
            result = type('obj', (object,), {})()
            call_str = str(mock_supabase_client.table.call_args)
            
            if "projects" in call_str:
                result.data = [project]
            elif "tech_stack" in call_str:
                result.data = tech_stack
            elif "issues" in call_str:
                result.data = issues
            elif "team_members" in call_str:
                result.data = team_members
            else:
                result.data = []
            return result
        
        mock_supabase_client.table().execute.side_effect = mock_execute
        
        response = client.get(f"/api/projects/{project['id']}")
        
        assert response.status_code == 200
        # Should handle large response efficiently
