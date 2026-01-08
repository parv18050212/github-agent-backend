"""
Unit Tests for CRUD Operations
"""
import pytest
from uuid import UUID, uuid4
from datetime import datetime
from backend.crud import (
    ProjectCRUD, AnalysisJobCRUD, TechStackCRUD, 
    IssueCRUD, TeamMemberCRUD
)


class TestProjectCRUD:
    """Test ProjectCRUD operations"""
    
    def test_create_project_success(self, mock_supabase_client, sample_project_data):
        """Test successful project creation"""
        # Setup mock
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        # Execute
        result = ProjectCRUD.create_project(
            repo_url=sample_project_data["repo_url"],
            team_name=sample_project_data["team_name"]
        )
        
        # Assert
        assert result is not None
        assert result["repo_url"] == sample_project_data["repo_url"]
        assert result["team_name"] == sample_project_data["team_name"]
        assert result["status"] == "pending"
        
        # Verify Supabase was called correctly
        mock_supabase_client.table.assert_called_with("projects")
    
    def test_create_project_without_team_name(self, mock_supabase_client, sample_project_data):
        """Test project creation without team name"""
        sample_project_data["team_name"] = None
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        result = ProjectCRUD.create_project(repo_url=sample_project_data["repo_url"])
        
        assert result is not None
        assert result["team_name"] is None
    
    def test_create_project_failure(self, mock_supabase_client):
        """Test project creation failure"""
        mock_supabase_client.table().execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception) as exc_info:
            ProjectCRUD.create_project(repo_url="https://github.com/test/repo")
        
        assert "Database error" in str(exc_info.value)
    
    def test_get_project_by_id(self, mock_supabase_client, sample_project_data):
        """Test getting project by ID"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        project_id = UUID(sample_project_data["id"])
        result = ProjectCRUD.get_project(project_id)
        
        assert result is not None
        assert result["id"] == sample_project_data["id"]
    
    def test_get_project_not_found(self, mock_supabase_client):
        """Test getting non-existent project"""
        mock_supabase_client.table().execute.return_value.data = []
        
        result = ProjectCRUD.get_project(uuid4())
        
        assert result is None
    
    def test_get_project_by_url(self, mock_supabase_client, sample_project_data):
        """Test getting project by URL"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        result = ProjectCRUD.get_project_by_url(sample_project_data["repo_url"])
        
        assert result is not None
        assert result["repo_url"] == sample_project_data["repo_url"]
    
    def test_update_project(self, mock_supabase_client, sample_project_data):
        """Test updating project"""
        updated_data = sample_project_data.copy()
        updated_data["status"] = "completed"
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        project_id = UUID(sample_project_data["id"])
        result = ProjectCRUD.update_project(project_id, {"status": "completed"})
        
        assert result is not None
        assert result["status"] == "completed"
    
    def test_update_project_status(self, mock_supabase_client, sample_project_data):
        """Test updating project status"""
        updated_data = sample_project_data.copy()
        updated_data["status"] = "analyzing"
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        project_id = UUID(sample_project_data["id"])
        result = ProjectCRUD.update_project_status(project_id, "analyzing")
        
        assert result is not None
        assert result["status"] == "analyzing"
    
    def test_update_project_scores(self, mock_supabase_client, sample_project_data):
        """Test updating project scores"""
        scores = {
            "total_score": 85.5,
            "originality_score": 90.0,
            "quality_score": 80.0
        }
        updated_data = sample_project_data.copy()
        updated_data.update(scores)
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        project_id = UUID(sample_project_data["id"])
        result = ProjectCRUD.update_project_scores(project_id, scores)
        
        assert result is not None
        assert result["total_score"] == 85.5
    
    def test_list_projects_no_filters(self, mock_supabase_client, sample_project_data):
        """Test listing projects without filters"""
        mock_result = type('obj', (object,), {'data': [sample_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        projects, total = ProjectCRUD.list_projects()
        
        assert len(projects) == 1
        assert total == 1
        assert projects[0]["id"] == sample_project_data["id"]
    
    def test_list_projects_with_status_filter(self, mock_supabase_client, completed_project_data):
        """Test listing projects filtered by status"""
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        projects, total = ProjectCRUD.list_projects(status="completed")
        
        assert len(projects) == 1
        assert projects[0]["status"] == "completed"
    
    def test_list_projects_with_score_filters(self, mock_supabase_client, completed_project_data):
        """Test listing projects with score filters"""
        mock_result = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        projects, total = ProjectCRUD.list_projects(min_score=70.0, max_score=90.0)
        
        assert len(projects) == 1
        assert 70.0 <= projects[0]["total_score"] <= 90.0
    
    def test_list_projects_pagination(self, mock_supabase_client, sample_project_data):
        """Test project list pagination"""
        mock_result = type('obj', (object,), {'data': [sample_project_data], 'count': 50})()
        mock_supabase_client.table().execute.return_value = mock_result
        
        projects, total = ProjectCRUD.list_projects(page=2, page_size=10)
        
        assert total == 50
    
    def test_delete_project(self, mock_supabase_client, sample_project_data):
        """Test deleting project"""
        mock_supabase_client.table().execute.return_value.data = [sample_project_data]
        
        project_id = UUID(sample_project_data["id"])
        result = ProjectCRUD.delete_project(project_id)
        
        assert result is True
    
    def test_delete_project_not_found(self, mock_supabase_client):
        """Test deleting non-existent project"""
        mock_supabase_client.table().execute.return_value.data = []
        
        result = ProjectCRUD.delete_project(uuid4())
        
        assert result is False
    
    def test_get_leaderboard_default(self, mock_supabase_client, completed_project_data):
        """Test getting leaderboard with defaults"""
        # Setup mock to return data with count
        mock_execute = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_table = mock_supabase_client.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.not_.is_.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.execute.return_value = mock_execute
        
        leaderboard, total = ProjectCRUD.get_leaderboard()
        
        assert isinstance(leaderboard, list)
        assert isinstance(total, int)
    
    def test_get_leaderboard_custom_sort(self, mock_supabase_client, completed_project_data):
        """Test leaderboard with custom sorting"""
        # Setup mock to return data with count
        mock_execute = type('obj', (object,), {'data': [completed_project_data], 'count': 1})()
        mock_table = mock_supabase_client.table.return_value
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.not_.is_.return_value = mock_table
        mock_table.range.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.execute.return_value = mock_execute
        
        leaderboard, total = ProjectCRUD.get_leaderboard(
            sort_by="originality_score",
            order="asc"
        )
        
        assert isinstance(leaderboard, list)
        assert isinstance(total, int)


class TestAnalysisJobCRUD:
    """Test AnalysisJobCRUD operations"""
    
    def test_create_job(self, mock_supabase_client, sample_job_data):
        """Test creating analysis job"""
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        project_id = UUID(sample_job_data["project_id"])
        result = AnalysisJobCRUD.create_job(project_id)
        
        assert result is not None
        assert result["project_id"] == str(project_id)
        assert result["status"] == "queued"
        assert result["progress"] == 0
    
    def test_get_job_by_id(self, mock_supabase_client, sample_job_data):
        """Test getting job by ID"""
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        job_id = UUID(sample_job_data["id"])
        result = AnalysisJobCRUD.get_job(job_id)
        
        assert result is not None
        assert result["id"] == str(job_id)
    
    def test_get_job_by_project(self, mock_supabase_client, sample_job_data):
        """Test getting latest job for project"""
        mock_supabase_client.table().execute.return_value.data = [sample_job_data]
        
        project_id = UUID(sample_job_data["project_id"])
        result = AnalysisJobCRUD.get_job_by_project(project_id)
        
        assert result is not None
        assert result["project_id"] == str(project_id)
    
    def test_update_job_progress(self, mock_supabase_client, sample_job_data):
        """Test updating job progress"""
        updated_data = sample_job_data.copy()
        updated_data["progress"] = 50
        updated_data["current_stage"] = "quality_check"
        updated_data["status"] = "running"
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        job_id = UUID(sample_job_data["id"])
        result = AnalysisJobCRUD.update_job_progress(job_id, 50, "quality_check")
        
        assert result is not None
        assert result["progress"] == 50
        assert result["current_stage"] == "quality_check"
        assert result["status"] == "running"
    
    def test_update_job_progress_without_stage(self, mock_supabase_client, sample_job_data):
        """Test updating progress without stage"""
        updated_data = sample_job_data.copy()
        updated_data["progress"] = 75
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        job_id = UUID(sample_job_data["id"])
        result = AnalysisJobCRUD.update_job_progress(job_id, 75)
        
        assert result is not None
        assert result["progress"] == 75
    
    def test_complete_job(self, mock_supabase_client, sample_job_data):
        """Test completing job"""
        updated_data = sample_job_data.copy()
        updated_data["status"] = "completed"
        updated_data["progress"] = 100
        updated_data["completed_at"] = datetime.now().isoformat()
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        job_id = UUID(sample_job_data["id"])
        result = AnalysisJobCRUD.complete_job(job_id)
        
        assert result is not None
        assert result["status"] == "completed"
        assert result["progress"] == 100
        assert result["completed_at"] is not None
    
    def test_fail_job(self, mock_supabase_client, sample_job_data):
        """Test failing job"""
        updated_data = sample_job_data.copy()
        updated_data["status"] = "failed"
        updated_data["error_message"] = "Test error"
        updated_data["completed_at"] = datetime.now().isoformat()
        mock_supabase_client.table().execute.return_value.data = [updated_data]
        
        job_id = UUID(sample_job_data["id"])
        result = AnalysisJobCRUD.fail_job(job_id, "Test error")
        
        assert result is not None
        assert result["status"] == "failed"
        assert result["error_message"] == "Test error"
        assert result["completed_at"] is not None


class TestTechStackCRUD:
    """Test TechStackCRUD operations"""
    
    def test_add_technologies(self, mock_supabase_client, sample_tech_stack):
        """Test adding technologies"""
        mock_supabase_client.table().execute.return_value.data = sample_tech_stack
        
        project_id = UUID(sample_tech_stack[0]["project_id"])
        technologies = [
            {"technology": "Python", "category": "language"},
            {"technology": "FastAPI", "category": "framework"}
        ]
        
        result = TechStackCRUD.add_technologies(project_id, technologies)
        
        assert result is not None
        assert len(result) == 2
    
    def test_get_tech_stack(self, mock_supabase_client, sample_tech_stack):
        """Test getting tech stack"""
        mock_supabase_client.table().execute.return_value.data = sample_tech_stack
        
        project_id = UUID(sample_tech_stack[0]["project_id"])
        result = TechStackCRUD.get_tech_stack(project_id)
        
        assert len(result) == 2
        assert result[0]["technology"] == "Python"


class TestIssueCRUD:
    """Test IssueCRUD operations"""
    
    def test_add_issues(self, mock_supabase_client, sample_issues):
        """Test adding issues"""
        mock_supabase_client.table().execute.return_value.data = sample_issues
        
        project_id = UUID(sample_issues[0]["project_id"])
        issues = [
            {
                "type": "security",
                "severity": "high",
                "file_path": "config.py",
                "description": "API key exposed",
                "ai_probability": None,
                "plagiarism_score": None
            }
        ]
        
        result = IssueCRUD.add_issues(project_id, issues)
        
        assert result is not None
        assert len(result) >= 1
    
    def test_get_issues(self, mock_supabase_client, sample_issues):
        """Test getting issues"""
        mock_supabase_client.table().execute.return_value.data = sample_issues
        
        project_id = UUID(sample_issues[0]["project_id"])
        result = IssueCRUD.get_issues(project_id)
        
        assert len(result) == 2
        assert result[0]["type"] == "security"


class TestTeamMemberCRUD:
    """Test TeamMemberCRUD operations"""
    
    def test_add_members(self, mock_supabase_client, sample_team_members):
        """Test adding team members"""
        mock_supabase_client.table().execute.return_value.data = sample_team_members
        
        project_id = UUID(sample_team_members[0]["project_id"])
        members = [
            {"name": "John Doe", "commits": 25, "contribution_pct": 55.6}
        ]
        
        result = TeamMemberCRUD.add_members(project_id, members)
        
        assert result is not None
        assert len(result) >= 1
    
    def test_get_team_members(self, mock_supabase_client, sample_team_members):
        """Test getting team members"""
        mock_supabase_client.table().execute.return_value.data = sample_team_members
        
        project_id = UUID(sample_team_members[0]["project_id"])
        result = TeamMemberCRUD.get_team_members(project_id)
        
        assert len(result) == 2
        assert result[0]["name"] == "John Doe"
        assert result[0]["commits"] == 25
