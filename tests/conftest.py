"""
Pytest Configuration and Fixtures
"""
import pytest
import os
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Mock environment variables for testing
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-key"
os.environ["SUPABASE_SERVICE_KEY"] = "test-service-key"
os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["GITHUB_API_KEY"] = "test-github-key"

# Patch Supabase at import time to prevent real connections
_mock_supabase_client = None

def _get_mock_supabase():
    """Get or create mock Supabase client"""
    global _mock_supabase_client
    if _mock_supabase_client is None:
        _mock_supabase_client = MagicMock()
        mock_table = MagicMock()
        _mock_supabase_client.table.return_value = mock_table
        
        # Setup chainable methods
        mock_table.select.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.delete.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.gte.return_value = mock_table
        mock_table.lte.return_value = mock_table
        mock_table.ilike.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.range.return_value = mock_table
        
        # Default execute response
        mock_execute = MagicMock()
        mock_execute.data = []
        mock_execute.count = 0
        mock_table.execute.return_value = mock_execute
        
    return _mock_supabase_client

# Patch Supabase client creation before any imports
sys.modules['supabase'] = MagicMock()
sys.modules['supabase'].create_client = lambda *args, **kwargs: _get_mock_supabase()


# ==================== Fixtures ====================

@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for unit tests"""
    mock_client = _get_mock_supabase()
    
    # Reset the mock for each test
    mock_client.reset_mock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    
    # Setup chainable methods
    mock_table.select.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.delete.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.ilike.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.range.return_value = mock_table
    
    # Default execute response
    mock_execute = MagicMock()
    mock_execute.data = []
    mock_execute.count = 0
    mock_table.execute.return_value = mock_execute
    
    return mock_client


@pytest.fixture
def sample_project_data():
    """Sample project data for testing"""
    return {
        "id": str(uuid4()),
        "repo_url": "https://github.com/test/repo",
        "team_name": "Test Team",
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "analyzed_at": None,
        "total_score": None,
        "originality_score": None,
        "quality_score": None,
        "security_score": None,
        "effort_score": None,
        "implementation_score": None,
        "engineering_score": None,
        "organization_score": None,
        "documentation_score": None,
        "total_commits": None,
        "verdict": None,
        "ai_pros": None,
        "ai_cons": None,
        "report_json": None,
        "viz_url": None
    }


@pytest.fixture
def completed_project_data(sample_project_data):
    """Sample completed project with scores"""
    sample_project_data.update({
        "status": "completed",
        "analyzed_at": datetime.now().isoformat(),
        "total_score": 78.5,
        "originality_score": 85.0,
        "quality_score": 72.0,
        "security_score": 90.0,
        "effort_score": 65.0,
        "implementation_score": 80.0,
        "engineering_score": 75.0,
        "organization_score": 70.0,
        "documentation_score": 68.0,
        "total_commits": 45,
        "verdict": "Production Ready",
        "ai_pros": "Good architecture",
        "ai_cons": "Needs more tests"
    })
    return sample_project_data


@pytest.fixture
def sample_job_data():
    """Sample analysis job data"""
    project_id = str(uuid4())
    return {
        "id": str(uuid4()),
        "project_id": project_id,
        "status": "queued",
        "progress": 0,
        "current_stage": None,
        "error_message": None,
        "started_at": datetime.now().isoformat(),
        "completed_at": None
    }


@pytest.fixture
def sample_tech_stack():
    """Sample tech stack data"""
    project_id = str(uuid4())
    return [
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "technology": "Python",
            "category": "language"
        },
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "technology": "FastAPI",
            "category": "framework"
        }
    ]


@pytest.fixture
def sample_issues():
    """Sample issues data"""
    project_id = str(uuid4())
    return [
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "type": "security",
            "severity": "high",
            "file_path": "config.py",
            "description": "API key exposed",
            "ai_probability": None,
            "plagiarism_score": None
        },
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "type": "plagiarism",
            "severity": "medium",
            "file_path": "utils.py",
            "description": "High AI probability",
            "ai_probability": 0.75,
            "plagiarism_score": None
        }
    ]


@pytest.fixture
def sample_team_members():
    """Sample team members data"""
    project_id = str(uuid4())
    return [
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "name": "John Doe",
            "commits": 25,
            "contribution_pct": 55.6
        },
        {
            "id": str(uuid4()),
            "project_id": project_id,
            "name": "Jane Smith",
            "commits": 20,
            "contribution_pct": 44.4
        }
    ]


@pytest.fixture
def sample_analysis_report():
    """Sample analysis report from agent.py"""
    return {
        "repo": "https://github.com/test/repo",
        "stack": ["Python", "FastAPI", "PostgreSQL"],
        "scores": {
            "originality": 85.0,
            "quality": 72.0,
            "security": 90.0,
            "effort": 65.0,
            "implementation": 80.0,
            "engineering": 75.0,
            "organization": 70.0,
            "documentation": 68.0
        },
        "team": {
            "John Doe": 25,
            "Jane Smith": 20
        },
        "total_commits": 45,
        "files": [
            {
                "name": "main.py",
                "ai_pct": 15.0,
                "plag_pct": 10.0,
                "risk": 13.0,
                "match": ""
            },
            {
                "name": "utils.py",
                "ai_pct": 75.0,
                "plag_pct": 20.0,
                "risk": 53.0,
                "match": "helpers.py"
            }
        ],
        "security": {
            "score": 90,
            "leaked_keys": [
                {"type": "API Key", "file": "config.py"}
            ]
        },
        "judge": {
            "project_name": "Test Project",
            "description": "A test project",
            "features": ["Feature 1", "Feature 2"],
            "implementation_score": 80,
            "positive_feedback": "Good architecture",
            "constructive_feedback": "Needs more tests",
            "verdict": "Production Ready"
        },
        "maturity": {
            "score": 75
        },
        "commit_details": {
            "author_stats": {
                "John Doe": {"commits": 25},
                "Jane Smith": {"commits": 20}
            }
        },
        "structure": {
            "organization_score": 70
        },
        "quality_metrics": {
            "maintainability_index": 72,
            "documentation_score": 68
        },
        "viz": "scorecard.png"
    }


@pytest.fixture
def mock_progress_tracker(monkeypatch):
    """Mock progress tracker"""
    mock_tracker = MagicMock()
    
    from backend.utils import progress_tracker
    monkeypatch.setattr(progress_tracker, "ProgressTracker", lambda job_id: mock_tracker)
    
    return mock_tracker


@pytest.fixture
def mock_data_mapper(monkeypatch):
    """Mock data mapper"""
    mock_mapper = MagicMock()
    mock_mapper.save_analysis_results.return_value = True
    
    from backend.services import data_mapper
    monkeypatch.setattr(data_mapper, "DataMapper", mock_mapper)
    
    return mock_mapper


# ==================== Migration Test Fixtures ====================

@pytest.fixture
def sample_batch():
    """Sample batch data for testing"""
    return {
        "id": str(uuid4()),
        "name": "3rd Year AIML 2025",
        "semester": "6th Sem",
        "year": "2025",
        "created_at": datetime.now().isoformat()
    }


@pytest.fixture
def sample_team_with_analysis(sample_batch):
    """Sample team with complete analysis data"""
    return {
        "id": str(uuid4()),
        "batch_id": sample_batch["id"],
        "team_name": "Test Team with Analysis",
        "repo_url": "https://github.com/test/analyzed-repo",
        "status": "completed",
        "total_score": 85.5,
        "quality_score": 90.0,
        "security_score": 80.0,
        "originality_score": 85.0,
        "documentation_score": 88.0,
        "architecture_score": 82.0,
        "last_analyzed_at": datetime.now().isoformat(),
        "analyzed_at": datetime.now().isoformat(),
        "created_at": datetime.now().isoformat(),
        "report_json": {
            "commit_details": {
                "all_commits": [
                    {
                        "hash": "abc123",
                        "author": "John Doe",
                        "email": "john@example.com",
                        "message": "Initial commit",
                        "date": datetime.now().isoformat(),
                        "additions": 100,
                        "deletions": 0,
                        "files_changed": ["main.py", "README.md"]
                    }
                ],
                "total_commits": 1
            },
            "structure": {
                "file_count": 10,
                "loc": 1000,
                "architecture": "MVC"
            },
            "languages": {
                "Python": 80.0,
                "JavaScript": 20.0
            },
            "stack": ["Python", "FastAPI", "PostgreSQL"]
        },
        "team_members": [
            {
                "id": str(uuid4()),
                "name": "John Doe",
                "commits": 25,
                "contribution_pct": 55.6
            },
            {
                "id": str(uuid4()),
                "name": "Jane Smith",
                "commits": 20,
                "contribution_pct": 44.4
            }
        ]
    }


@pytest.fixture
async def test_client():
    """HTTP test client for integration tests"""
    from httpx import AsyncClient
    from src.api.backend.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Authentication headers for test requests"""
    # In real tests, this would use a valid test token
    return {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_user():
    """Sample admin user"""
    return {
        "user_id": str(uuid4()),
        "email": "admin@test.com",
        "role": "admin"
    }


@pytest.fixture
def mentor_user():
    """Sample mentor user"""
    return {
        "user_id": str(uuid4()),
        "email": "mentor@test.com",
        "role": "mentor"
    }
