#!/usr/bin/env python3
"""Test query with last_analyzed_at after migration"""
import json
from src.api.backend.database import get_supabase

sb = get_supabase()
mentor_id = '78b61cf6-042f-4a1f-af25-d9ae75ce622e'

print("Testing query WITH last_analyzed_at (after migration):")
print("=" * 70)

try:
    # Test the exact query from teams.py
    query_str = '''
    *,
    batches(id, name, semester, year),
    students(count),
    projects(id, total_score, status, last_analyzed_at)
    '''
    result = sb.table('teams').select(query_str, count='exact').eq('mentor_id', mentor_id).execute()
    print(f"\n✅ Query SUCCESS!")
    print(f"Found {len(result.data)} teams (count: {result.count})")
    
    if result.data:
        print(f"\nTeams:")
        for team in result.data:
            print(f"  - {team.get('team_name')}")
            print(f"    ID: {team.get('id')}")
            projects = team.get('projects')
            if projects:
                print(f"    Last analyzed: {projects.get('last_analyzed_at')}")
    else:
        print("\n⚠️ NO TEAMS FOUND!")
        print("Checking if teams still exist...")
        simple = sb.table('teams').select('id, team_name, mentor_id').eq('mentor_id', mentor_id).execute()
        print(f"Simple query found {len(simple.data)} teams")
    
except Exception as e:
    print(f"\n❌ Query FAILED: {e}")
    print("\nTrying without last_analyzed_at...")
    try:
        query_str = '''
        *,
        batches(id, name, semester, year),
        students(count),
        projects(id, total_score, status)
        '''
        result = sb.table('teams').select(query_str).eq('mentor_id', mentor_id).execute()
        print(f"✅ Works without last_analyzed_at: {len(result.data)} teams")
    except Exception as e2:
        print(f"❌ Still fails: {e2}")

print("\n" + "=" * 70)
