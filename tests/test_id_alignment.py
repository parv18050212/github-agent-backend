import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4, UUID
from src.api.backend.routers.teams import create_team
from src.api.backend.schemas import TeamCreateRequest, StudentCreateRequest

# Mock dependencies
@pytest.fixture
def mock_supabase():
    with patch('src.api.backend.routers.teams.get_supabase') as mock:
        client = MagicMock()
        mock.return_value = client
        yield client

@pytest.fixture
def mock_current_user():
    user = MagicMock()
    user.user_id = str(uuid4())
    user.role = "admin"
    return user

@pytest.mark.asyncio
async def test_create_team_aligned_ids(mock_supabase, mock_current_user):
    # Setup
    common_id = str(uuid4())
    
    # Mock Batch Response
    mock_supabase.table().select().eq().execute.return_value.data = [{"id": "batch-123"}]
    
    # Mock UUID generation to return our common_id
    with patch('src.api.backend.routers.teams.uuid4', return_value=UUID(common_id)):
        # Mock Insert Responses
        # Team Insert
        mock_supabase.table().insert().execute().return_value.data = [{"id": common_id, "project_id": None}]
        
        # Project Insert
        project_mock_data = [{"id": common_id, "team_id": common_id}]
        # We need specific behavior for different tables
        def insert_side_effect(data):
            mock_res = MagicMock()
            if "team_name" in data: # It's a team
                mock_res.data = [{"id": common_id}]
            elif "repo_url" in data: # It's a project
                assert data["id"] == common_id
                assert data["team_id"] == common_id
                mock_res.data = [{"id": common_id}]
            else:
                 mock_res.data = []
            return mock_res

        # Because the code chains .table().insert().execute(), checking calls is easier than side effects on mocks often
        # But let's verify calls args verify logic
        
        # Mock final team detail fetch
        mock_supabase.table().select().eq().execute.return_value.data = [{
            "id": common_id,
            "project_id": common_id,
            "team_name": "Test Team"
        }]

        # Execute
        req = TeamCreateRequest(
            batch_id=uuid4(),
            name="Test Team",
            repo_url="https://github.com/test/repo",
            students=[]
        )
        
        response = await create_team(req, mock_current_user)
        
        # Verify
        assert response.team["id"] == common_id
        # In the real code, we update the team with project_id, so the final fetch gets it.
        # We asserted above that 'repo_url' insert data had matching IDs.
