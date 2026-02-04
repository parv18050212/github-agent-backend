#!/usr/bin/env python3
"""Test fixed query"""
import json
from src.api.backend.database import get_supabase

sb = get_supabase()
mentor_id = '78b61cf6-042f-4a1f-af25-d9ae75ce622e'

print("Testing FIXED query for paragagarwal8131@gmail.com:")
print("=" * 70)

try:
    query_str = '''
    *,
    batches(id, name, semester, year),
    students(count),
    projects(id, total_score, status)
    '''
    result = sb.table('teams').select(query_str, count='exact').eq('mentor_id', mentor_id).execute()
    print(f"\n✅ Query SUCCESS!")
    print(f"Found {len(result.data)} teams (count: {result.count})")
    print(f"\nTeams:")
    for team in result.data:
        print(f"  - {team.get('team_name')}")
        print(f"    ID: {team.get('id')}")
        batch = team.get('batches', [])
        if batch:
            batch_data = batch[0] if isinstance(batch, list) else batch
            print(f"    Batch: {batch_data.get('name')}")
    
    print(f"\n\nFull Response:")
    print(json.dumps(result.data, indent=2, default=str))
    
except Exception as e:
    print(f"\n❌ Query FAILED: {e}")

print("\n" + "=" * 70)
