# Running Migration Tests

## Overview
This document explains how to run the tests for the teams/projects table migration.

## Test Files

### 1. API Tests (`test_teams_migration.py`)
Tests the unified teams API endpoints after migration.

**Test Classes:**
- `TestTeamsAPI` - Tests teams CRUD operations with analysis fields
- `TestTeamsAnalytics` - Tests analytics endpoints
- `TestMigrationDataIntegrity` - Tests data integrity after migration
- `TestBackwardCompatibility` - Tests backward compatibility

**Coverage:**
- ✅ GET /api/teams includes analysis fields
- ✅ GET /api/teams/{id} returns complete data
- ✅ POST /api/teams/{id}/analyze works
- ✅ /api/projects/* returns 404
- ✅ Team analytics endpoint
- ✅ Team commits endpoint
- ✅ Team file tree endpoint
- ✅ Data integrity checks
- ✅ Score validation
- ✅ Backward compatibility

## Running Tests

### Run All Migration Tests
```bash
cd "proj-github agent"
pytest tests/integration/test_teams_migration.py -v
```

### Run Specific Test Class
```bash
pytest tests/integration/test_teams_migration.py::TestTeamsAPI -v
```

### Run Specific Test
```bash
pytest tests/integration/test_teams_migration.py::TestTeamsAPI::test_get_teams_includes_analysis_fields -v
```

### Run with Coverage
```bash
pytest tests/integration/test_teams_migration.py --cov=src.api.backend --cov-report=html
```

## Prerequisites

### 1. Install Dependencies
```bash
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx
```

### 2. Set Environment Variables
```bash
# Copy .env.example to .env and fill in values
cp .env.example .env
```

Required variables:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_SERVICE_KEY`
- `GITHUB_API_KEY`
- `GEMINI_API_KEY`

### 3. Database Setup
Ensure the migration has been applied:
```bash
python scripts/migrate_projects_to_teams.py
```

## Test Environment

### Using Test Database
For integration tests, it's recommended to use a separate test database:

1. Create a test project in Supabase
2. Set test environment variables:
```bash
export SUPABASE_URL="https://your-test-project.supabase.co"
export SUPABASE_KEY="your-test-anon-key"
export SUPABASE_SERVICE_KEY="your-test-service-key"
```

### Using Mocks
Unit tests use mocked Supabase clients (see `conftest.py`).

## Expected Results

### All Tests Passing
```
tests/integration/test_teams_migration.py::TestTeamsAPI::test_get_teams_includes_analysis_fields PASSED
tests/integration/test_teams_migration.py::TestTeamsAPI::test_get_team_by_id_returns_complete_data PASSED
tests/integration/test_teams_migration.py::TestTeamsAPI::test_analyze_team_endpoint PASSED
tests/integration/test_teams_migration.py::TestTeamsAPI::test_projects_endpoints_return_404 PASSED
...
======================== X passed in Y.YYs ========================
```

### Coverage Report
Target: >80% coverage for modified files
- `src/api/backend/routers/teams.py`
- `src/api/backend/routers/analytics.py`
- `src/api/backend/crud.py`
- `src/api/backend/services/data_mapper.py`

## Troubleshooting

### Test Failures

**Issue: Connection errors**
```
Solution: Check SUPABASE_URL and keys are correct
```

**Issue: 404 errors on /api/teams**
```
Solution: Ensure backend server is running or using test client correctly
```

**Issue: Missing fixtures**
```
Solution: Check conftest.py has all required fixtures
```

### Common Issues

1. **Import Errors**
   - Ensure you're in the correct directory
   - Check Python path includes project root

2. **Database Errors**
   - Verify migration was applied successfully
   - Check database connection

3. **Authentication Errors**
   - Verify test tokens are valid
   - Check auth middleware configuration

## Continuous Integration

### GitHub Actions
Add to `.github/workflows/test.yml`:
```yaml
- name: Run Migration Tests
  run: |
    cd "proj-github agent"
    pytest tests/integration/test_teams_migration.py -v
```

### Pre-commit Hook
Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
cd "proj-github agent"
pytest tests/integration/test_teams_migration.py --tb=short
```

## Next Steps

After tests pass:
1. Run full test suite: `pytest tests/ -v`
2. Check coverage: `pytest --cov=src --cov-report=html`
3. Review coverage report: `open htmlcov/index.html`
4. Deploy to staging
5. Run smoke tests on staging
6. Deploy to production

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Supabase Python Client](https://supabase.com/docs/reference/python/introduction)
- [Migration Design Document](../../.kiro/specs/merge-teams-projects-tables/design.md)

