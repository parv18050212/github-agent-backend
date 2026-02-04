#!/usr/bin/env python3
"""
Test suite for Phase 5: Analytics & Reports APIs
Tests team analytics, commit history, file trees, and report generation.

Usage:
    python test_phase5.py
"""

import requests
from typing import Optional
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 10


class Colors:
    """Terminal colors"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.END}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.END}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓{Colors.END} {text}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗{Colors.END} {text}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ{Colors.END} {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠{Colors.END} {text}")


def get_token() -> str:
    """Get authentication token from user"""
    print_header("Authentication")
    print(f"{Colors.BOLD}Please provide your authentication token:{Colors.END}")
    print_info("This should be a Google ID token or Supabase access token")
    print_info("You can get this token using get_token.html or get_token_helper.py")
    print()
    token = input("Token: ").strip()
    return token


def make_request(
    method: str,
    endpoint: str,
    token: str,
    data: Optional[dict] = None,
    params: Optional[dict] = None
) -> tuple[bool, dict]:
    """Make API request and return (success, response_data)"""
    url = f"{BASE_URL}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=TIMEOUT)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=TIMEOUT)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, json=data, timeout=TIMEOUT)
        else:
            return False, {"error": f"Unsupported method: {method}"}
        
        # Try to parse JSON response
        try:
            response_data = response.json()
        except:
            response_data = {"text": response.text}
        
        if response.status_code in [200, 201]:
            return True, response_data
        else:
            return False, {
                "status_code": response.status_code,
                "error": response_data
            }
    
    except requests.exceptions.Timeout:
        return False, {"error": "Request timeout"}
    except requests.exceptions.ConnectionError:
        return False, {"error": "Connection error - is the server running?"}
    except Exception as e:
        return False, {"error": str(e)}


def test_team_analytics(token: str, team_id: str):
    """Test team analytics endpoint"""
    print_header("Testing Team Analytics")
    
    print(f"{Colors.BOLD}GET /api/teams/{team_id}/analytics{Colors.END}")
    success, response = make_request("GET", f"/api/teams/{team_id}/analytics", token)
    
    if success:
        print_success("Team analytics retrieved successfully")
        
        # Display key metrics
        if "analysis" in response:
            print(f"\n{Colors.BOLD}Analysis Scores:{Colors.END}")
            analysis = response["analysis"]
            print(f"  Total Score: {analysis.get('totalScore', 0)}")
            print(f"  Quality: {analysis.get('qualityScore', 0)}")
            print(f"  Security: {analysis.get('securityScore', 0)}")
            print(f"  Originality: {analysis.get('originalityScore', 0)}")
        
        if "commits" in response:
            commits = response["commits"]
            print(f"\n{Colors.BOLD}Commit Metrics:{Colors.END}")
            print(f"  Total Commits: {commits.get('total', 0)}")
            print(f"  Last Week: {commits.get('lastWeek', 0)}")
            print(f"  Contributors: {len(commits.get('contributionDistribution', []))}")
            print(f"  Burst Detected: {commits.get('burstDetected', False)}")
        
        if "codeMetrics" in response:
            code = response["codeMetrics"]
            print(f"\n{Colors.BOLD}Code Metrics:{Colors.END}")
            print(f"  Files: {code.get('totalFiles', 0)}")
            print(f"  Lines of Code: {code.get('totalLinesOfCode', 0)}")
            print(f"  Architecture: {code.get('architecturePattern', 'Unknown')}")
        
        if "security" in response:
            security = response["security"]
            print(f"\n{Colors.BOLD}Security:{Colors.END}")
            print(f"  Score: {security.get('score', 0)}")
            print(f"  Issues: {len(security.get('issues', []))}")
            print(f"  Secrets Detected: {security.get('secretsDetected', 0)}")
        
        print(f"\n{Colors.BOLD}Health Status:{Colors.END} {response.get('healthStatus', 'Unknown')}")
        
        return True
    else:
        print_error("Failed to get team analytics")
        print(json.dumps(response, indent=2))
        return False


def test_team_commits(token: str, team_id: str):
    """Test team commits endpoint"""
    print_header("Testing Team Commits")
    
    # Test 1: Get all commits
    print(f"{Colors.BOLD}GET /api/teams/{team_id}/commits{Colors.END}")
    success, response = make_request("GET", f"/api/teams/{team_id}/commits", token)
    
    if success:
        total = response.get('total', 0)
        print_success(f"Retrieved {total} commits")
        
        if response.get('commits'):
            print(f"\n{Colors.BOLD}Recent Commits:{Colors.END}")
            for commit in response['commits'][:3]:  # Show first 3
                print(f"  {commit['sha'][:8]} - {commit['author']}: {commit['message'][:50]}")
    else:
        print_error("Failed to get commits")
        print(json.dumps(response, indent=2))
        return False
    
    # Test 2: Pagination
    print(f"\n{Colors.BOLD}GET /api/teams/{team_id}/commits?page=1&pageSize=5{Colors.END}")
    success, response = make_request("GET", f"/api/teams/{team_id}/commits", token, params={"page": 1, "pageSize": 5})
    
    if success:
        print_success(f"Pagination works: {len(response.get('commits', []))} commits returned")
        return True
    else:
        print_error("Failed pagination test")
        return False


def test_team_file_tree(token: str, team_id: str):
    """Test team file tree endpoint"""
    print_header("Testing Team File Tree")
    
    print(f"{Colors.BOLD}GET /api/teams/{team_id}/file-tree{Colors.END}")
    success, response = make_request("GET", f"/api/teams/{team_id}/file-tree", token)
    
    if success:
        print_success("File tree retrieved successfully")
        
        total_files = response.get('totalFiles', 0)
        total_size = response.get('totalSize', 0)
        
        print(f"\n{Colors.BOLD}Repository Structure:{Colors.END}")
        print(f"  Total Files: {total_files}")
        print(f"  Total Size: {total_size:,} bytes ({total_size / 1024:.1f} KB)")
        
        if response.get('tree'):
            print(f"\n{Colors.BOLD}Directory Structure:{Colors.END}")
            for item in response['tree'][:5]:  # Show first 5 items
                if item['type'] == 'directory':
                    print(f"  📁 {item['path']}/ ({len(item.get('children', []))} items)")
                else:
                    size = item.get('size', 0)
                    print(f"  📄 {item['path']} ({size} bytes)")
        
        return True
    else:
        print_error("Failed to get file tree")
        print(json.dumps(response, indent=2))
        return False


def test_batch_report(token: str, batch_id: str):
    """Test batch report endpoint"""
    print_header("Testing Batch Report")
    
    print(f"{Colors.BOLD}GET /api/reports/batch/{batch_id}{Colors.END}")
    success, response = make_request("GET", f"/api/reports/batch/{batch_id}", token)
    
    if success:
        print_success("Batch report generated successfully")
        
        if "summary" in response:
            summary = response["summary"]
            print(f"\n{Colors.BOLD}Batch Summary:{Colors.END}")
            print(f"  Total Teams: {summary.get('totalTeams', 0)}")
            print(f"  Average Score: {summary.get('averageScore', 0):.2f}")
            print(f"  Top Team: {summary.get('topTeam', 'N/A')}")
            print(f"  Top Score: {summary.get('topScore', 0):.2f}")
        
        if "insights" in response:
            insights = response["insights"]
            print(f"\n{Colors.BOLD}Insights:{Colors.END}")
            print(f"  Most Used Tech: {insights.get('mostUsedTech', 'Unknown')}")
            print(f"  Average AI Usage: {insights.get('averageAiUsage', 0):.2f}%")
            print(f"  Security Issues: {insights.get('totalSecurityIssues', 0)}")
        
        if "teams" in response and response["teams"]:
            print(f"\n{Colors.BOLD}Top 3 Teams:{Colors.END}")
            for team in response["teams"][:3]:
                print(f"  {team['rank']}. {team['teamName']} - {team['totalScore']:.2f}")
        
        return True
    else:
        print_error("Failed to generate batch report")
        print(json.dumps(response, indent=2))
        return False


def test_mentor_report(token: str, mentor_id: str):
    """Test mentor report endpoint"""
    print_header("Testing Mentor Report")
    
    print(f"{Colors.BOLD}GET /api/reports/mentor/{mentor_id}{Colors.END}")
    success, response = make_request("GET", f"/api/reports/mentor/{mentor_id}", token)
    
    if success:
        print_success("Mentor report generated successfully")
        
        if "summary" in response:
            summary = response["summary"]
            print(f"\n{Colors.BOLD}Mentor Summary:{Colors.END}")
            print(f"  Total Teams: {summary.get('totalTeams', 0)}")
            print(f"  Average Score: {summary.get('averageScore', 0):.2f}")
            print(f"  Teams On Track: {summary.get('teamsOnTrack', 0)}")
            print(f"  Teams At Risk: {summary.get('teamsAtRisk', 0)}")
            if 'teamsCritical' in summary:
                print(f"  Teams Critical: {summary.get('teamsCritical', 0)}")
        
        if "teams" in response:
            print(f"\n{Colors.BOLD}Assigned Teams:{Colors.END}")
            for team in response["teams"]:
                print(f"  {team['teamName']} - {team['totalScore']:.2f} ({team['healthStatus']})")
        
        return True
    else:
        print_error("Failed to generate mentor report")
        print(json.dumps(response, indent=2))
        return False


def test_team_report(token: str, team_id: str):
    """Test team report endpoint"""
    print_header("Testing Team Report")
    
    print(f"{Colors.BOLD}GET /api/reports/team/{team_id}{Colors.END}")
    success, response = make_request("GET", f"/api/reports/team/{team_id}", token)
    
    if success:
        print_success("Team report generated successfully")
        
        print(f"\n{Colors.BOLD}Team: {response.get('teamName', 'Unknown')}{Colors.END}")
        print(f"Batch: {response.get('batchId', 'Unknown')}")
        print(f"Generated: {response.get('generatedAt', 'Unknown')}")
        
        if "analysis" in response:
            analysis = response["analysis"]
            print(f"\n{Colors.BOLD}Scores:{Colors.END}")
            print(f"  Total: {analysis.get('totalScore', 0):.2f}")
            print(f"  Quality: {analysis.get('qualityScore', 0):.2f}")
            print(f"  Security: {analysis.get('securityScore', 0):.2f}")
        
        return True
    else:
        print_error("Failed to generate team report")
        print(json.dumps(response, indent=2))
        return False


def main():
    """Main test runner"""
    print_header("Phase 5: Analytics & Reports Test Suite")
    print_info("This test suite validates Team Analytics and Reports endpoints")
    print()
    
    # Get authentication token
    token = get_token()
    
    # Verify authentication
    print_header("Verifying Authentication")
    success, response = make_request("GET", "/api/auth/me", token)
    
    if not success:
        print_error("Authentication failed")
        print(json.dumps(response, indent=2))
        return
    
    user_role = response.get("role", "unknown")
    user_name = response.get("full_name", response.get("email", "Unknown"))
    user_id = response.get("user_id")
    print_success(f"Authenticated as: {user_name}")
    print_info(f"Role: {user_role}")
    
    # Get a team ID to test with
    print_header("Getting Test Team")
    
    if user_role == "admin":
        # Get first team from any batch
        success, batches = make_request("GET", "/api/batches", token)
        if not success or not batches.get("batches"):
            print_error("No batches found. Please create a batch first.")
            return
        
        batch_id = batches["batches"][0]["id"]
        success, teams = make_request("GET", "/api/teams", token, params={"batchId": batch_id})
    else:
        # Get mentor's teams
        success, teams = make_request("GET", "/api/mentor/teams", token)
    
    if not success or not teams.get("teams"):
        print_error("No teams found. Please create teams first.")
        return
    
    team_id = teams["teams"][0]["id"]
    team_name = teams["teams"][0]["name"]
    batch_id = teams["teams"][0].get("batchId", teams["teams"][0].get("batch_id"))
    
    print_success(f"Using team: {team_name} (ID: {team_id})")
    
    # Run tests
    results = []
    
    # Analytics tests
    results.append(("Team Analytics", test_team_analytics(token, team_id)))
    results.append(("Team Commits", test_team_commits(token, team_id)))
    results.append(("Team File Tree", test_team_file_tree(token, team_id)))
    
    # Reports tests
    results.append(("Team Report", test_team_report(token, team_id)))
    
    if user_role == "admin":
        # Admin-only tests
        results.append(("Batch Report", test_batch_report(token, batch_id)))
    else:
        # Mentor report (using own ID)
        results.append(("Mentor Report", test_mentor_report(token, user_id)))
    
    # Print summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}")
        else:
            print_error(f"{test_name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print_success("All tests passed!")
    else:
        print_error(f"{total - passed} test(s) failed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
