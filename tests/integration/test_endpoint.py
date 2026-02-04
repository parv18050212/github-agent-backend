#!/usr/bin/env python3
"""Test the actual /api/teams endpoint"""
import json
import sys
from src.api.backend.routers.teams import list_teams
from src.api.backend.middleware import AuthUser
from unittest.mock import Mock

# Mock the current user (mentor)
mock_user = AuthUser(
    user_id='78b61cf6-042f-4a1f-af25-d9ae75ce622e',
    email='paragagarwal8131@gmail.com',
    role='mentor'
)

print("Testing /api/teams endpoint as mentor:")
print("=" * 70)

try:
    # Call the endpoint function directly
    import asyncio
    result = asyncio.run(list_teams(
        batch_id=None,
        status=None,
        mentor_id=None,
        search=None,
        page=1,
        page_size=20,
        sort='name',
        current_user=mock_user
    ))
    
    print(f"\n✅ Endpoint returned successfully!")
    print(f"Teams count: {result.total}")
    print(f"Teams in response: {len(result.teams)}")
    
    if result.teams:
        print("\nTeams:")
        for team in result.teams:
            print(f"  - {team.get('team_name', 'Unknown')}")
            print(f"    ID: {team.get('id')}")
    else:
        print("\n⚠️ Response has ZERO teams!")
        
    print(f"\nFull response:")
    print(json.dumps({
        'teams': result.teams[:1] if result.teams else [],  # Just first team
        'total': result.total,
        'page': result.page,
        'page_size': result.page_size
    }, indent=2, default=str))
    
except Exception as e:
    print(f"\n❌ Endpoint failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
