#!/usr/bin/env python3
"""Test script to check if commit_forensics is returning all_commits"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.detectors.commit_forensics import analyze_commits
import json

# Test with a local repo path
repo_path = input("Enter repository path to test (or press Enter for default test repo): ").strip()
if not repo_path:
    # Use the report directory as a test - it should have git history
    repo_path = os.path.join(os.path.dirname(__file__), "report")

print(f"\nAnalyzing: {repo_path}\n")

result = analyze_commits(repo_path)

print("=" * 80)
print("COMMIT ANALYSIS RESULTS")
print("=" * 80)

print(f"\nTotal Commits: {result.get('total_commits', 0)}")
print(f"Branches: {len(result.get('branches', []))}")
print(f"\nAuthor Stats: {len(result.get('author_stats', {}))}")

for author, stats in result.get('author_stats', {}).items():
    print(f"  - {author}: {stats.get('commits', 0)} commits, {stats.get('lines_changed', 0)} lines")

print(f"\n{'='*80}")
print(f"ALL_COMMITS KEY EXISTS: {'all_commits' in result}")
print(f"ALL_COMMITS COUNT: {len(result.get('all_commits', []))}")
print(f"{'='*80}")
if 'error' in result:
    print(f"\n❌ ERROR: {result['error']}")
if result.get('all_commits'):
    print("\nFirst 3 commits:")
    for i, commit in enumerate(result.get('all_commits', [])[:3]):
        print(f"\n  Commit {i+1}:")
        print(f"    Hash: {commit.get('short_hash')}")
        print(f"    Author: {commit.get('author')}")
        print(f"    Message: {commit.get('message', '')[:60]}...")
        print(f"    Files: {len(commit.get('files_changed', []))}")
        print(f"    +{commit.get('additions', 0)} -{commit.get('deletions', 0)}")
else:
    print("\n⚠️  WARNING: all_commits list is EMPTY or missing!")
    print("\nFull result keys:", list(result.keys()))

print("\n" + "=" * 80)
