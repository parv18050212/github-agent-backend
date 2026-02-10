"""
Integration Tests for Teams Migration
Tests the unified teams table after merging projects into teams.
"""
import pytest
import httpx
from uuid import uuid4


class TestTeamsAPI:
    """Test Teams API endpoints after migration"""
    
    @pytest.mark.asyncio
    async def test_get_teams_includes_analysis_fields(self, test_client, auth_headers, sample_batch):
        """Test GET /api/teams returns analysis fields"""
        # Create a team with analysis data
        team_data = {
            "batch_id": sample_batch["id"],
            "team_name": "Test Team Alpha",
            "repo_url": "https://github.com/test/repo-alpha",
            "total_score": 85.5,
            "quality_score": 90.0,
            "security_score": 80.0,
            "originality_score": 85.0,
            "documentation_score": 88.0,
            "architecture_score": 82.0,
            "status": "completed",
            "last_analyzed_at": "2025-02-11T10:00:00Z"
        }
        
        # Create team via API
        response = await test_client.post(
            "/api/teams",
            json=team_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_team = response.json()
        
        # Get teams list
        response = await test_client.get(
            f"/api/teams?batch_id={sample_batch['id']}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify analysis fields are included
        assert "teams" in data
        assert len(data["teams"]) > 0
        
        team = next((t for t in data["teams"] if t["id"] == created_team["id"]), None)
        assert team is not None
        assert "total_score" in team
        assert "quality_score" in team
        assert "security_score" in team
        assert "originality_score" in team
        assert "documentation_score" in team
        assert "architecture_score" in team
        assert "status" in team
        assert "last_analyzed_at" in team
        
        # Verify values
        assert team["total_score"] == 85.5
        assert team["quality_score"] == 90.0
        assert team["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_get_team_by_id_returns_complete_data(self, test_client, auth_headers, sample_batch):
        """Test GET /api/teams/{id} returns complete team data"""
        # Create a team
        team_data = {
            "batch_id": sample_batch["id"],
            "team_name": "Test Team Beta",
            "repo_url": "https://github.com/test/repo-beta",
            "total_score": 92.0,
            "status": "completed"
        }
        
        response = await test_client.post(
            "/api/teams",
            json=team_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_team = response.json()
        team_id = created_team["id"]
        
        # Get team by ID
        response = await test_client.get(
            f"/api/teams/{team_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        team = response.json()
        
        # Verify complete data
        assert team["id"] == team_id
        assert team["team_name"] == "Test Team Beta"
        assert team["repo_url"] == "https://github.com/test/repo-beta"
        assert team["total_score"] == 92.0
        assert team["status"] == "completed"
        assert "batch_id" in team
        assert "created_at" in team
    
    @pytest.mark.asyncio
    async def test_analyze_team_endpoint(self, test_client, auth_headers, sample_batch):
        """Test POST /api/teams/{id}/analyze works"""
        # Create a team with repo URL
        team_data = {
            "batch_id": sample_batch["id"],
            "team_name": "Test Team Gamma",
            "repo_url": "https://github.com/test/repo-gamma"
        }
        
        response = await test_client.post(
            "/api/teams",
            json=team_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_team = response.json()
        team_id = created_team["id"]
        
        # Trigger analysis
        response = await test_client.post(
            f"/api/teams/{team_id}/analyze",
            headers=auth_headers
        )
        
        # Should queue analysis successfully
        assert response.status_code in [200, 202]
        data = response.json()
        assert "job_id" in data or "message" in data
    
    @pytest.mark.asyncio
    async def test_projects_endpoints_return_404(self, test_client, auth_headers):
        """Test /api/projects/* endpoints return 404"""
        # Test various project endpoints
        endpoints = [
            "/api/projects",
            f"/api/projects/{uuid4()}",
            f"/api/projects/{uuid4()}/analyze"
        ]
        
        for endpoint in endpoints:
            response = await test_client.get(endpoint, headers=auth_headers)
            assert response.status_code == 404, f"Endpoint {endpoint} should return 404"
    
    @pytest.mark.asyncio
    async def test_team_without_analysis_data(self, test_client, auth_headers, sample_batch):
        """Test team without analysis data (pending status)"""
        # Create a team without analysis
        team_data = {
            "batch_id": sample_batch["id"],
            "team_name": "Test Team Delta",
            "repo_url": "https://github.com/test/repo-delta"
        }
        
        response = await test_client.post(
            "/api/teams",
            json=team_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_team = response.json()
        
        # Verify default values
        assert created_team["status"] in [None, "pending"]
        assert created_team.get("total_score") in [None, 0]
        assert created_team.get("last_analyzed_at") is None
    
    @pytest.mark.asyncio
    async def test_update_team_analysis_fields(self, test_client, auth_headers, sample_batch):
        """Test updating team analysis fields"""
        # Create a team
        team_data = {
            "batch_id": sample_batch["id"],
            "team_name": "Test Team Epsilon",
            "repo_url": "https://github.com/test/repo-epsilon"
        }
        
        response = await test_client.post(
            "/api/teams",
            json=team_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_team = response.json()
        team_id = created_team["id"]
        
        # Update analysis fields
        update_data = {
            "total_score": 88.0,
            "quality_score": 85.0,
            "status": "completed"
        }
        
        response = await test_client.put(
            f"/api/teams/{team_id}",
            json=update_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        updated_team = response.json()
        
        # Verify updates
        assert updated_team["total_score"] == 88.0
        assert updated_team["quality_score"] == 85.0
        assert updated_team["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_team_list_filtering_by_status(self, test_client, auth_headers, sample_batch):
        """Test filtering teams by analysis status"""
        # Create teams with different statuses
        teams_data = [
            {
                "batch_id": sample_batch["id"],
                "team_name": "Completed Team",
                "status": "completed",
                "total_score": 90.0
            },
            {
                "batch_id": sample_batch["id"],
                "team_name": "Pending Team",
                "status": "pending"
            },
            {
                "batch_id": sample_batch["id"],
                "team_name": "Analyzing Team",
                "status": "analyzing"
            }
        ]
        
        for team_data in teams_data:
            await test_client.post("/api/teams", json=team_data, headers=auth_headers)
        
        # Filter by completed status
        response = await test_client.get(
            f"/api/teams?batch_id={sample_batch['id']}&status=completed",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify only completed teams returned
        assert all(team["status"] == "completed" for team in data["teams"])
    
    @pytest.mark.asyncio
    async def test_team_list_filtering_by_score(self, test_client, auth_headers, sample_batch):
        """Test filtering teams by score range"""
        # Create teams with different scores
        teams_data = [
            {
                "batch_id": sample_batch["id"],
                "team_name": "High Score Team",
                "total_score": 95.0,
                "status": "completed"
            },
            {
                "batch_id": sample_batch["id"],
                "team_name": "Medium Score Team",
                "total_score": 75.0,
                "status": "completed"
            },
            {
                "batch_id": sample_batch["id"],
                "team_name": "Low Score Team",
                "total_score": 55.0,
                "status": "completed"
            }
        ]
        
        for team_data in teams_data:
            await test_client.post("/api/teams", json=team_data, headers=auth_headers)
        
        # Filter by score range
        response = await test_client.get(
            f"/api/teams?batch_id={sample_batch['id']}&min_score=70&max_score=90",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify only teams in score range returned
        for team in data["teams"]:
            if team["total_score"]:
                assert 70 <= team["total_score"] <= 90


class TestTeamsAnalytics:
    """Test analytics endpoints with unified teams table"""
    
    @pytest.mark.asyncio
    async def test_team_analytics_endpoint(self, test_client, auth_headers, sample_team_with_analysis):
        """Test GET /api/teams/{id}/analytics"""
        team_id = sample_team_with_analysis["id"]
        
        response = await test_client.get(
            f"/api/teams/{team_id}/analytics",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify analytics structure
        assert "teamId" in data
        assert "analysis" in data
        assert "commits" in data
        assert "codeMetrics" in data
        assert "security" in data
        assert "aiAnalysis" in data
        
        # Verify analysis scores
        assert "totalScore" in data["analysis"]
        assert "qualityScore" in data["analysis"]
        assert "securityScore" in data["analysis"]
    
    @pytest.mark.asyncio
    async def test_team_commits_endpoint(self, test_client, auth_headers, sample_team_with_analysis):
        """Test GET /api/teams/{id}/commits"""
        team_id = sample_team_with_analysis["id"]
        
        response = await test_client.get(
            f"/api/teams/{team_id}/commits?page=1&pageSize=10",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify commits structure
        assert "commits" in data
        assert "total" in data
        assert "page" in data
        assert "pageSize" in data
        assert isinstance(data["commits"], list)
    
    @pytest.mark.asyncio
    async def test_team_file_tree_endpoint(self, test_client, auth_headers, sample_team_with_analysis):
        """Test GET /api/teams/{id}/file-tree"""
        team_id = sample_team_with_analysis["id"]
        
        response = await test_client.get(
            f"/api/teams/{team_id}/file-tree",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify file tree structure
        assert "tree" in data
        assert "totalFiles" in data
        assert "totalSize" in data
        assert isinstance(data["tree"], list)


class TestMigrationDataIntegrity:
    """Test data integrity after migration"""
    
    @pytest.mark.asyncio
    async def test_no_orphaned_team_members(self, test_client, auth_headers):
        """Test that all team members reference valid teams"""
        # This would query the database directly
        # For now, we'll test via API
        response = await test_client.get("/api/teams", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        for team in data.get("teams", []):
            if "team_members" in team and team["team_members"]:
                # Verify each member has valid team_id
                for member in team["team_members"]:
                    assert "team_id" in member or "id" in member
    
    @pytest.mark.asyncio
    async def test_all_teams_have_required_fields(self, test_client, auth_headers):
        """Test that all teams have required fields"""
        response = await test_client.get("/api/teams", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["id", "team_name", "batch_id", "created_at"]
        
        for team in data.get("teams", []):
            for field in required_fields:
                assert field in team, f"Team missing required field: {field}"
    
    @pytest.mark.asyncio
    async def test_score_ranges_valid(self, test_client, auth_headers):
        """Test that all scores are within valid ranges (0-100)"""
        response = await test_client.get("/api/teams", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        score_fields = [
            "total_score", "quality_score", "security_score",
            "originality_score", "documentation_score", "architecture_score"
        ]
        
        for team in data.get("teams", []):
            for field in score_fields:
                if field in team and team[field] is not None:
                    score = team[field]
                    assert 0 <= score <= 100, f"Invalid {field}: {score}"


class TestBackwardCompatibility:
    """Test backward compatibility after migration"""
    
    @pytest.mark.asyncio
    async def test_celery_tasks_use_team_id(self, test_client, auth_headers, sample_batch):
        """Test that Celery tasks work with team_id"""
        # Create a team
        team_data = {
            "batch_id": sample_batch["id"],
            "team_name": "Celery Test Team",
            "repo_url": "https://github.com/test/celery-test"
        }
        
        response = await test_client.post(
            "/api/teams",
            json=team_data,
            headers=auth_headers
        )
        assert response.status_code == 201
        created_team = response.json()
        team_id = created_team["id"]
        
        # Trigger analysis (which uses Celery)
        response = await test_client.post(
            f"/api/teams/{team_id}/analyze",
            headers=auth_headers
        )
        
        # Should work without errors
        assert response.status_code in [200, 202]
    
    @pytest.mark.asyncio
    async def test_bulk_import_creates_teams_only(self, test_client, auth_headers, sample_batch):
        """Test that bulk import creates only team records"""
        # This would test the bulk import endpoint
        # Verify it creates teams with all necessary fields
        pass  # Implement based on your bulk import API


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
