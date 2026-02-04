#!/usr/bin/env python3
"""Comprehensive test of entire mentor teams flow"""
import json
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("COMPREHENSIVE MENTOR TEAMS FLOW TEST")
print("=" * 80)

# Test 1: Database query
print("\n1. Testing direct database query...")
print("-" * 80)
from supabase import create_client
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

mentor_id = '78b61cf6-042f-4a1f-af25-d9ae75ce622e'
result = sb.table('teams').select(
    '*',
    count='exact'
).eq('mentor_id', mentor_id).execute()

print(f"✓ Database query: Found {result.count} teams")
if result.data:
    print(f"  Teams: {[t['team_name'] for t in result.data]}")

# Test 2: Endpoint query with sorting
print("\n2. Testing endpoint query with default sort='team_name'...")
print("-" * 80)
result2 = sb.table('teams').select(
    """
    *,
    batches!inner(id, name, semester, year),
    students(count),
    projects(id, total_score, status, last_analyzed_at),
    team_members:projects(team_members(count))
    """,
    count='exact'
).eq('mentor_id', mentor_id).order('team_name').execute()

print(f"✓ Endpoint query with sorting: Found {result2.count} teams")
if result2.data:
    print(f"  Teams: {[t['team_name'] for t in result2.data]}")

# Test 3: API endpoint simulation
print("\n3. Testing API endpoint function...")
print("-" * 80)
from src.api.backend.routers.teams import list_teams
from src.api.backend.middleware import AuthUser
import asyncio

mock_user = AuthUser(
    user_id='78b61cf6-042f-4a1f-af25-d9ae75ce622e',
    email='paragagarwal8131@gmail.com',
    role='mentor'
)

try:
    result3 = asyncio.run(list_teams(
        batch_id=None,
        status=None,
        mentor_id=None,
        search=None,
        page=1,
        page_size=20,
        sort='team_name',  # Use correct column name
        current_user=mock_user
    ))
    
    print(f"✓ API endpoint: Returned {result3.total} teams")
    print(f"  Response structure:")
    print(f"    - teams: {len(result3.teams)} items")
    print(f"    - total: {result3.total}")
    print(f"    - page: {result3.page}")
    print(f"    - page_size: {result3.page_size}")
    
    if result3.teams:
        print(f"\n  First team sample:")
        team = result3.teams[0]
        print(f"    - id: {team.get('id')}")
        print(f"    - team_name: {team.get('team_name')}")
        print(f"    - mentor_id: {team.get('mentor_id')}")
        print(f"    - student_count: {team.get('student_count')}")
        print(f"    - health_status: {team.get('health_status')}")
        print(f"    - mentor_name: {team.get('mentor_name')}")
        
        # Check nested data
        if 'batches' in team:
            print(f"    - batches: {team['batches']}")
        if 'projects' in team:
            print(f"    - projects: {team['projects']}")
    
    print(f"\n  JSON response preview:")
    print(json.dumps({
        'teams': result3.teams[:1],
        'total': result3.total,
        'page': result3.page,
        'page_size': result3.page_size,
        'total_pages': result3.total_pages
    }, indent=2, default=str))
    
except Exception as e:
    print(f"✗ API endpoint failed: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Check response format matches frontend expectations
print("\n4. Validating response format for frontend...")
print("-" * 80)
if result3.teams:
    required_fields = ['id', 'team_name', 'batch_id', 'health_status', 'student_count']
    team = result3.teams[0]
    
    missing = [f for f in required_fields if f not in team]
    if missing:
        print(f"✗ Missing required fields: {missing}")
    else:
        print(f"✓ All required fields present")
    
    # Check for snake_case vs camelCase
    print(f"\n  Field name check:")
    print(f"    - 'team_name' exists: {'team_name' in team}")
    print(f"    - 'teamName' exists: {'teamName' in team}")
    print(f"    - 'health_status' exists: {'health_status' in team}")
    print(f"    - 'healthStatus' exists: {'healthStatus' in team}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
