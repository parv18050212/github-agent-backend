#!/usr/bin/env python3
"""Test script to check mentor team queries"""
import json
from src.api.backend.database import get_supabase

def test_mentor_teams():
    sb = get_supabase()
    mentor_id = '78b61cf6-042f-4a1f-af25-d9ae75ce622e'
    
    print("=" * 60)
    print("Testing Mentor Team Queries")
    print("=" * 60)
    
    # Test 1: Simple query without joins
    print("\n1. Simple teams query for mentor:")
    result1 = sb.table('teams').select('*').eq('mentor_id', mentor_id).execute()
    print(f"   Found {len(result1.data)} teams")
    for team in result1.data:
        print(f"   - {team['team_name']} (batch_id: {team.get('batch_id')})")
    
    # Test 2: Query with inner join on batches
    print("\n2. Teams query with batches inner join:")
    try:
        query_str = '*, batches!inner(id, name, semester, year), students(count), projects(id, total_score, last_analyzed_at, status)'
        result2 = sb.table('teams').select(query_str).eq('mentor_id', mentor_id).execute()
        print(f"   Found {len(result2.data)} teams")
        for team in result2.data:
            batch_info = team.get('batches', {})
            print(f"   - {team['team_name']} -> Batch: {batch_info.get('name', 'N/A')}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Test 3: Check if batch exists
    print("\n3. Checking batch existence:")
    batch_id = result1.data[0].get('batch_id') if result1.data else None
    if batch_id:
        batch_result = sb.table('batches').select('*').eq('id', batch_id).execute()
        if batch_result.data:
            print(f"   Batch found: {batch_result.data[0].get('name')}")
        else:
            print(f"   WARNING: Batch {batch_id} not found!")
    
    # Test 4: Full query as used in endpoint
    print("\n4. Full endpoint query:")
    try:
        full_query = '''
        *,
        batches!inner(id, name, semester, year),
        students(count),
        projects(id, total_score, last_analyzed_at, status),
        team_members:projects(team_members(count))
        '''
        result4 = sb.table('teams').select(full_query, count='exact').eq('mentor_id', mentor_id).execute()
        print(f"   Found {len(result4.data)} teams (count: {result4.count})")
        print(f"\n   Full response:")
        print(json.dumps(result4.data, indent=2, default=str))
    except Exception as e:
        print(f"   ERROR: {e}")

if __name__ == '__main__':
    test_mentor_teams()
