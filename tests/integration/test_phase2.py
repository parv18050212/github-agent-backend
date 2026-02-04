"""
Phase 2 - Team Management Testing Script
Tests all team-related endpoints
"""
import requests
import json
from datetime import datetime
import sys

BASE_URL = "http://localhost:8000"

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BLUE = '\033[94m'
CYAN = '\033[96m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text:^70}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_info(text):
    print(f"{CYAN}ℹ {text}{RESET}")


def test_list_teams(access_token, batch_id):
    """Test GET /api/teams"""
    print_header("Testing List Teams")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"batch_id": batch_id} if batch_id else {}
        
        response = requests.get(
            f"{BASE_URL}/api/teams",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved {data['total']} teams")
            print_info(f"Page: {data['page']}/{data['total_pages']}")
            
            for i, team in enumerate(data['teams'][:3], 1):
                print_info(f"{i}. {team.get('team_name', 'N/A')} - {team.get('health_status', 'N/A')}")
            
            return data['teams']
        else:
            print_error(f"Failed to list teams: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_create_team(access_token, batch_id):
    """Test POST /api/teams"""
    print_header("Testing Create Team")
    
    team_data = {
        "batch_id": batch_id,
        "name": f"Test Team {datetime.now().strftime('%H:%M:%S')}",
        "repo_url": "https://github.com/test-team/test-project",
        "description": "Test team for Phase 2 testing",
        "students": [
            {
                "name": "Test Student 1",
                "email": "student1@test.com",
                "github_username": "student1"
            },
            {
                "name": "Test Student 2",
                "email": "student2@test.com",
                "github_username": "student2"
            }
        ]
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(
            f"{BASE_URL}/api/teams",
            json=team_data,
            headers=headers
        )
        
        if response.status_code == 201 or response.status_code == 200:
            data = response.json()
            print_success("Team created successfully!")
            team = data.get('team', data)
            print_info(f"ID: {team.get('id')}")
            print_info(f"Name: {team.get('team_name')}")
            print_info(f"Students: {len(team_data['students'])}")
            return team.get('id')
        elif response.status_code == 403:
            print_warning("Access denied - Admin role required")
            return None
        else:
            print_error(f"Failed to create team: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_get_team(access_token, team_id):
    """Test GET /api/teams/{team_id}"""
    print_header("Testing Get Team Details")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/teams/{team_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Team details retrieved!")
            print_info(f"Name: {data.get('team_name')}")
            print_info(f"Health Status: {data.get('health_status')}")
            print_info(f"Students: {len(data.get('students', []))}")
            return True
        else:
            print_error(f"Failed to get team: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_update_team(access_token, team_id):
    """Test PUT /api/teams/{team_id}"""
    print_header("Testing Update Team")
    
    update_data = {
        "health_status": "at_risk",
        "risk_flags": ["low_activity", "missing_commits"]
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.put(
            f"{BASE_URL}/api/teams/{team_id}",
            json=update_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Team updated successfully!")
            team = data.get('team', data)
            print_info(f"New health status: {team.get('health_status')}")
            return True
        elif response.status_code == 403:
            print_warning("Access denied - Admin role required")
            return False
        else:
            print_error(f"Failed to update team: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_analyze_team(access_token, team_id):
    """Test POST /api/teams/{team_id}/analyze"""
    print_header("Testing Trigger Team Analysis")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(
            f"{BASE_URL}/api/teams/{team_id}/analyze",
            headers=headers,
            params={"force": False}
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Analysis triggered!")
            print_info(f"Job ID: {data.get('job_id')}")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Message: {data.get('message')}")
            return True
        else:
            print_error(f"Failed to trigger analysis: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_delete_team(access_token, team_id):
    """Test DELETE /api/teams/{team_id}"""
    print_header("Testing Delete Team")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.delete(
            f"{BASE_URL}/api/teams/{team_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            print_success("Team deleted successfully!")
            return True
        elif response.status_code == 403:
            print_warning("Access denied - Admin role required")
            return False
        else:
            print_error(f"Failed to delete team: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")


def main():
    """Run all Phase 2 team management tests"""
    print(f"\n{BLUE}{'='*70}")
    print(f"  PHASE 2 - TEAM MANAGEMENT TESTING")
    print(f"  Testing Team CRUD Operations")
    print(f"{'='*70}{RESET}\n")
    
    # Get authentication
    access_token = input(f"{CYAN}Enter your access token: {RESET}").strip()
    
    if not access_token:
        print_error("Access token is required")
        return
    
    # Get batch ID for admin users
    batch_id = input(f"{CYAN}Enter batch ID (or press Enter if you're a mentor): {RESET}").strip()
    
    # Run tests
    results = []
    
    # List teams
    teams = test_list_teams(access_token, batch_id if batch_id else None)
    results.append(("List Teams", teams is not None))
    
    # Create team (admin only)
    if batch_id:
        team_id = test_create_team(access_token, batch_id)
        if team_id:
            results.append(("Create Team", True))
            
            # Get team details
            results.append(("Get Team Details", test_get_team(access_token, team_id)))
            
            # Update team
            results.append(("Update Team", test_update_team(access_token, team_id)))
            
            # Trigger analysis
            results.append(("Trigger Analysis", test_analyze_team(access_token, team_id)))
            
            # Delete team
            cleanup = input(f"\n{CYAN}Delete test team? (y/n): {RESET}").lower()
            if cleanup == 'y':
                results.append(("Delete Team", test_delete_team(access_token, team_id)))
        else:
            results.append(("Create Team", False))
    else:
        # Mentor - test with first team from list
        if teams and len(teams) > 0:
            team_id = teams[0].get('id')
            results.append(("Get Team Details", test_get_team(access_token, team_id)))
            results.append(("Trigger Analysis", test_analyze_team(access_token, team_id)))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {name:.<50} {status}")
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    if passed == total:
        print(f"{GREEN}All {total} tests passed! ✓{RESET}")
    else:
        print(f"{YELLOW}{passed}/{total} tests passed{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")


if __name__ == "__main__":
    main()
