#!/usr/bin/env python3
"""
Test suite for Phase 4: Dashboard APIs
Tests admin and mentor dashboard endpoints.

Usage:
    python test_phase4.py
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


def test_admin_dashboard(token: str, batch_id: str):
    """Test admin dashboard endpoint"""
    print_header("Testing Admin Dashboard")
    
    print(f"{Colors.BOLD}GET /api/admin/dashboard?batchId={batch_id}{Colors.END}")
    success, response = make_request("GET", "/api/admin/dashboard", token, params={"batchId": batch_id})
    
    if success:
        print_success("Admin dashboard retrieved successfully")
        print(f"\n{Colors.BOLD}Dashboard Data:{Colors.END}")
        print(json.dumps(response, indent=2))
        
        # Validate response structure
        if "overview" in response:
            overview = response["overview"]
            print(f"\n{Colors.BOLD}Overview Statistics:{Colors.END}")
            print(f"  Total Teams: {overview.get('totalTeams', 0)}")
            print(f"  Active Teams: {overview.get('activeTeams', 0)}")
            print(f"  Total Mentors: {overview.get('totalMentors', 0)}")
            print(f"  Total Students: {overview.get('totalStudents', 0)}")
            print(f"  Unassigned Teams: {overview.get('unassignedTeams', 0)}")
        
        if "healthDistribution" in response:
            health = response["healthDistribution"]
            print(f"\n{Colors.BOLD}Health Distribution:{Colors.END}")
            print(f"  On Track: {health.get('onTrack', 0)}")
            print(f"  At Risk: {health.get('atRisk', 0)}")
            print(f"  Critical: {health.get('critical', 0)}")
        
        if "mentorWorkload" in response:
            print(f"\n{Colors.BOLD}Mentor Workload:{Colors.END}")
            for mentor in response["mentorWorkload"]:
                print(f"  {mentor['mentorName']}: {mentor['assignedTeams']} teams ({mentor['onTrack']} on track, {mentor['atRisk']} at risk)")
        
        return True
    else:
        print_error(f"Failed to get admin dashboard")
        print(json.dumps(response, indent=2))
        return False


def test_admin_users(token: str):
    """Test admin users endpoint"""
    print_header("Testing Admin Users Management")
    
    # Test 1: Get all users
    print(f"{Colors.BOLD}GET /api/admin/users{Colors.END}")
    success, response = make_request("GET", "/api/admin/users", token)
    
    if success:
        print_success(f"Retrieved {response.get('total', 0)} users")
        print(json.dumps(response, indent=2))
        return response.get('users', [])
    else:
        print_error("Failed to get users")
        print(json.dumps(response, indent=2))
        return []


def test_update_user_role(token: str, user_id: str):
    """Test updating user role"""
    print_header("Testing User Role Update")
    
    print(f"{Colors.BOLD}PUT /api/admin/users/{user_id}/role{Colors.END}")
    
    # First, get current role
    success, users_response = make_request("GET", "/api/admin/users", token)
    if not success:
        print_error("Cannot get users to test role update")
        return False
    
    # Test updating to mentor (if not already)
    data = {"role": "mentor"}
    success, response = make_request("PUT", f"/api/admin/users/{user_id}/role", token, data=data)
    
    if success:
        print_success("User role updated successfully")
        print(json.dumps(response, indent=2))
        return True
    else:
        print_error("Failed to update user role")
        print(json.dumps(response, indent=2))
        return False


def test_mentor_dashboard(token: str):
    """Test mentor dashboard endpoint"""
    print_header("Testing Mentor Dashboard")
    
    print(f"{Colors.BOLD}GET /api/mentor/dashboard{Colors.END}")
    success, response = make_request("GET", "/api/mentor/dashboard", token)
    
    if success:
        print_success("Mentor dashboard retrieved successfully")
        print(json.dumps(response, indent=2))
        
        # Validate response structure
        if "overview" in response:
            overview = response["overview"]
            print(f"\n{Colors.BOLD}Overview Statistics:{Colors.END}")
            print(f"  Total Teams: {overview.get('totalTeams', 0)}")
            print(f"  On Track: {overview.get('onTrack', 0)}")
            print(f"  At Risk: {overview.get('atRisk', 0)}")
            print(f"  Critical: {overview.get('critical', 0)}")
        
        if "teams" in response:
            print(f"\n{Colors.BOLD}Assigned Teams:{Colors.END}")
            for team in response["teams"]:
                print(f"  {team['name']} ({team['batchName']}) - {team['healthStatus']}")
        
        return True
    else:
        print_error("Failed to get mentor dashboard")
        print(json.dumps(response, indent=2))
        return False


def test_mentor_teams(token: str):
    """Test mentor teams endpoint"""
    print_header("Testing Mentor Teams Listing")
    
    # Test 1: Get all teams
    print(f"{Colors.BOLD}GET /api/mentor/teams{Colors.END}")
    success, response = make_request("GET", "/api/mentor/teams", token)
    
    if success:
        print_success(f"Retrieved {response.get('total', 0)} teams")
        print(json.dumps(response, indent=2))
    else:
        print_error("Failed to get mentor teams")
        print(json.dumps(response, indent=2))
        return False
    
    # Test 2: Filter by health status
    print(f"\n{Colors.BOLD}GET /api/mentor/teams?healthStatus=on_track{Colors.END}")
    success, response = make_request("GET", "/api/mentor/teams", token, params={"healthStatus": "on_track"})
    
    if success:
        print_success(f"Retrieved {response.get('total', 0)} on-track teams")
        print(json.dumps(response, indent=2))
    else:
        print_error("Failed to filter teams by health status")
        print(json.dumps(response, indent=2))
    
    # Test 3: Sort by last activity
    print(f"\n{Colors.BOLD}GET /api/mentor/teams?sort=lastActivity{Colors.END}")
    success, response = make_request("GET", "/api/mentor/teams", token, params={"sort": "lastActivity"})
    
    if success:
        print_success(f"Retrieved teams sorted by last activity")
        print(json.dumps(response, indent=2))
        return True
    else:
        print_error("Failed to sort teams")
        print(json.dumps(response, indent=2))
        return False


def main():
    """Main test runner"""
    print_header("Phase 4: Dashboard APIs Test Suite")
    print_info("This test suite validates Admin and Mentor dashboard endpoints")
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
    print_success(f"Authenticated as: {user_name}")
    print_info(f"Role: {user_role}")
    
    # Get batch ID for testing
    print_header("Getting Batch ID")
    success, batches_response = make_request("GET", "/api/batches", token)
    
    if not success or not batches_response.get("batches"):
        print_error("No batches found. Please create a batch first.")
        return
    
    batch_id = batches_response["batches"][0]["id"]
    batch_name = batches_response["batches"][0]["name"]
    print_success(f"Using batch: {batch_name} ({batch_id})")
    
    # Run tests based on role
    results = []
    
    if user_role == "admin":
        print_info("Running admin dashboard tests...")
        
        # Test admin dashboard
        results.append(("Admin Dashboard", test_admin_dashboard(token, batch_id)))
        
        # Test admin users
        users = test_admin_users(token)
        results.append(("Admin Users List", len(users) > 0))
        
        # Test user role update (if users exist)
        if users:
            user_id = users[0]["id"]
            results.append(("User Role Update", test_update_user_role(token, user_id)))
        
        # Also test mentor dashboard (admins can access mentor endpoints)
        print_info("Testing mentor dashboard as admin...")
        results.append(("Mentor Dashboard", test_mentor_dashboard(token)))
        results.append(("Mentor Teams", test_mentor_teams(token)))
    
    else:
        print_info("Running mentor dashboard tests...")
        
        # Test mentor dashboard
        results.append(("Mentor Dashboard", test_mentor_dashboard(token)))
        
        # Test mentor teams
        results.append(("Mentor Teams", test_mentor_teams(token)))
        
        # Inform user about admin-only tests
        print_warning("Admin-only tests skipped (requires admin role)")
    
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
