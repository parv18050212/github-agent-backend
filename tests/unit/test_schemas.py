"""
Unit Tests for Request/Response Schemas
"""
import pytest
from pydantic import ValidationError
from backend.schemas import (
    AnalyzeRepoRequest, BatchUploadRequest, ProjectFilterParams,
    LeaderboardParams, ScoreBreakdown, AnalysisResultResponse
)
from uuid import uuid4
from datetime import datetime


class TestAnalyzeRepoRequest:
    """Test AnalyzeRepoRequest validation"""
    
    def test_valid_github_url(self):
        """Test valid GitHub URL"""
        request = AnalyzeRepoRequest(
            repo_url="https://github.com/user/repo",
            team_name="Test Team"
        )
        
        assert request.repo_url == "https://github.com/user/repo"
        assert request.team_name == "Test Team"
    
    def test_valid_github_url_without_team(self):
        """Test valid request without team name"""
        request = AnalyzeRepoRequest(
            repo_url="https://github.com/user/repo"
        )
        
        assert request.repo_url == "https://github.com/user/repo"
        assert request.team_name is None
    
    def test_http_url_allowed(self):
        """Test HTTP URL is allowed"""
        request = AnalyzeRepoRequest(
            repo_url="http://github.com/user/repo"
        )
        
        assert request.repo_url.startswith("http://")
    
    def test_invalid_url_no_protocol(self):
        """Test URL without protocol fails"""
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRepoRequest(repo_url="github.com/user/repo")
        
        errors = exc_info.value.errors()
        assert any("http://" in str(e) for e in errors)
    
    def test_invalid_url_not_github(self):
        """Test non-GitHub URL fails"""
        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRepoRequest(repo_url="https://gitlab.com/user/repo")
        
        errors = exc_info.value.errors()
        assert any("github" in str(e).lower() for e in errors)
    
    def test_missing_repo_url(self):
        """Test missing repo_url fails"""
        with pytest.raises(ValidationError):
            AnalyzeRepoRequest()


class TestBatchUploadRequest:
    """Test BatchUploadRequest validation"""
    
    def test_valid_batch_request(self):
        """Test valid batch upload"""
        request = BatchUploadRequest(
            repos=[
                AnalyzeRepoRequest(
                    repo_url="https://github.com/user/repo1",
                    team_name="Team 1"
                ),
                AnalyzeRepoRequest(
                    repo_url="https://github.com/user/repo2",
                    team_name="Team 2"
                )
            ]
        )
        
        assert len(request.repos) == 2
    
    def test_batch_minimum_one_repo(self):
        """Test batch requires at least one repo"""
        with pytest.raises(ValidationError):
            BatchUploadRequest(repos=[])
    
    def test_batch_maximum_fifty_repos(self):
        """Test batch limited to 50 repos"""
        repos = [
            AnalyzeRepoRequest(repo_url=f"https://github.com/user/repo{i}")
            for i in range(51)
        ]
        
        with pytest.raises(ValidationError):
            BatchUploadRequest(repos=repos)
    
    def test_batch_exactly_fifty_repos_allowed(self):
        """Test batch of exactly 50 repos is allowed"""
        repos = [
            AnalyzeRepoRequest(repo_url=f"https://github.com/user/repo{i}")
            for i in range(50)
        ]
        
        request = BatchUploadRequest(repos=repos)
        assert len(request.repos) == 50


class TestProjectFilterParams:
    """Test ProjectFilterParams validation"""
    
    def test_default_values(self):
        """Test default filter parameters"""
        params = ProjectFilterParams()
        
        assert params.status is None
        assert params.min_score is None
        assert params.max_score is None
        assert params.page == 1
        assert params.page_size == 20
    
    def test_valid_score_range(self):
        """Test valid score range"""
        params = ProjectFilterParams(min_score=50.0, max_score=90.0)
        
        assert params.min_score == 50.0
        assert params.max_score == 90.0
    
    def test_invalid_min_score(self):
        """Test min_score out of range"""
        with pytest.raises(ValidationError):
            ProjectFilterParams(min_score=-10.0)
        
        with pytest.raises(ValidationError):
            ProjectFilterParams(min_score=110.0)
    
    def test_invalid_max_score(self):
        """Test max_score out of range"""
        with pytest.raises(ValidationError):
            ProjectFilterParams(max_score=-5.0)
        
        with pytest.raises(ValidationError):
            ProjectFilterParams(max_score=105.0)
    
    def test_page_minimum(self):
        """Test page must be >= 1"""
        with pytest.raises(ValidationError):
            ProjectFilterParams(page=0)
    
    def test_page_size_limits(self):
        """Test page_size limits"""
        with pytest.raises(ValidationError):
            ProjectFilterParams(page_size=0)
        
        with pytest.raises(ValidationError):
            ProjectFilterParams(page_size=101)
        
        # Valid boundary values
        params1 = ProjectFilterParams(page_size=1)
        assert params1.page_size == 1
        
        params2 = ProjectFilterParams(page_size=100)
        assert params2.page_size == 100


class TestLeaderboardParams:
    """Test LeaderboardParams validation"""
    
    def test_default_values(self):
        """Test default leaderboard parameters"""
        params = LeaderboardParams()
        
        assert params.sort_by == "total_score"
        assert params.order == "desc"
        assert params.page == 1
        assert params.page_size == 20
        assert params.status == "completed"
    
    def test_custom_sort_field(self):
        """Test custom sort field"""
        params = LeaderboardParams(sort_by="originality_score")
        
        assert params.sort_by == "originality_score"
    
    def test_ascending_order(self):
        """Test ascending order"""
        params = LeaderboardParams(order="asc")
        
        assert params.order == "asc"
    
    def test_status_filter(self):
        """Test status filter"""
        params = LeaderboardParams(status="completed")
        
        assert params.status == "completed"


class TestScoreBreakdown:
    """Test ScoreBreakdown model"""
    
    def test_all_scores_provided(self):
        """Test score breakdown with all scores"""
        scores = ScoreBreakdown(
            total_score=78.5,
            originality_score=85.0,
            quality_score=72.0,
            security_score=90.0,
            effort_score=65.0,
            implementation_score=80.0,
            engineering_score=75.0,
            organization_score=70.0,
            documentation_score=68.0
        )
        
        assert scores.total_score == 78.5
        assert scores.originality_score == 85.0
    
    def test_optional_scores(self):
        """Test score breakdown with missing scores"""
        scores = ScoreBreakdown(
            total_score=75.0
        )
        
        assert scores.total_score == 75.0
        assert scores.originality_score is None
        assert scores.quality_score is None
    
    def test_all_scores_none(self):
        """Test score breakdown with all None"""
        scores = ScoreBreakdown()
        
        assert scores.total_score is None
        assert scores.originality_score is None


class TestAnalysisResultResponse:
    """Test AnalysisResultResponse model"""
    
    def test_complete_response(self):
        """Test complete analysis result response"""
        response = AnalysisResultResponse(
            project_id=uuid4(),
            repo_url="https://github.com/user/repo",
            team_name="Test Team",
            status="completed",
            analyzed_at=datetime.now(),
            scores=ScoreBreakdown(total_score=85.0),
            total_commits=50,
            verdict="Production Ready",
            ai_pros="Great architecture",
            ai_cons="Needs more tests",
            tech_stack=[],
            issues=[],
            team_members=[],
            viz_url="scorecard.png",
            report_json={}
        )
        
        assert response.repo_url == "https://github.com/user/repo"
        assert response.team_name == "Test Team"
        assert response.verdict == "Production Ready"
    
    def test_minimal_response(self):
        """Test minimal valid response"""
        response = AnalysisResultResponse(
            project_id=uuid4(),
            repo_url="https://github.com/user/repo",
            status="pending",
            scores=ScoreBreakdown(),
            tech_stack=[],
            issues=[],
            team_members=[]
        )
        
        assert response.status == "pending"
        assert len(response.tech_stack) == 0


class TestSchemaEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_analyze_request_with_special_characters_in_url(self):
        """Test URL with special characters"""
        request = AnalyzeRepoRequest(
            repo_url="https://github.com/user/repo-name_123"
        )
        
        assert "repo-name_123" in request.repo_url
    
    def test_filter_params_boundary_scores(self):
        """Test boundary values for scores"""
        params = ProjectFilterParams(min_score=0.0, max_score=100.0)
        
        assert params.min_score == 0.0
        assert params.max_score == 100.0
    
    def test_leaderboard_params_with_all_custom(self):
        """Test leaderboard with all custom parameters"""
        params = LeaderboardParams(
            sort_by="quality_score",
            order="asc",
            page=5,
            page_size=50,
            status="completed"
        )
        
        assert params.sort_by == "quality_score"
        assert params.order == "asc"
        assert params.page == 5
        assert params.page_size == 50
    
    def test_score_breakdown_with_float_precision(self):
        """Test score breakdown with high precision floats"""
        scores = ScoreBreakdown(
            total_score=78.456789,
            originality_score=85.123456
        )
        
        assert scores.total_score == pytest.approx(78.456789)
        assert scores.originality_score == pytest.approx(85.123456)
