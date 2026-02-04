"""
Phase 3 - Mentor & Assignment Management Testing Script
Tests mentor CRUD and team assignment endpoints
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

def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")


def test_list_mentors(access_token):
    """Test GET /api/mentors"""
    print_header("Testing List Mentors")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BASE_URL}/api/mentors", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved {data['total']} mentors")
            
            for i, mentor in enumerate(data['mentors'][:3], 1):
                print_info(f"{i}. {mentor.get('full_name', 'N/A')} ({mentor.get('email')}) - {mentor.get('team_count', 0)} teams")
            
            return data['mentors']
        elif response.status_code == 403:
            print_warning("Access denied - Admin role required")
            return None
        else:
            print_error(f"Failed to list mentors: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_create_mentor(access_token):
    """Test POST /api/mentors"""
    print_header("Testing Create Mentor")
    
    mentor_data = {
        "email": f"testmentor{datetime.now().strftime('%H%M%S')}@example.com",
        "full_name": f"Test Mentor {datetime.now().strftime('%H:%M:%S')}",
        "status": "active"
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(
            f"{BASE_URL}/api/mentors",
            json=mentor_data,
            headers=headers
        )
        
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            print_success("Mentor created successfully!")
            print_info(f"Email: {mentor_data['email']}")
            print_info(f"Message: {data.get('message')}")
            return mentor_data['email']
        elif response.status_code == 403:
            print_warning("Access denied - Admin role required")
            return None
        else:
            print_error(f"Failed to create mentor: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_get_mentor(access_token, mentor_id):
    """Test GET /api/mentors/{mentor_id}"""
    print_header("Testing Get Mentor Details")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/mentors/{mentor_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Mentor details retrieved!")
            print_info(f"Name: {data.get('full_name')}")
            print_info(f"Email: {data.get('email')}")
            print_info(f"Teams: {data.get('team_count', 0)}")
            print_info(f"Batches: {len(data.get('batches', []))}")
            return True
        else:
            print_error(f"Failed to get mentor: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_update_mentor(access_token, mentor_id):
    """Test PUT /api/mentors/{mentor_id}"""
    print_header("Testing Update Mentor")
    
    update_data = {
        "full_name": f"Updated Mentor {datetime.now().strftime('%H:%M:%S')}"
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.put(
            f"{BASE_URL}/api/mentors/{mentor_id}",
            json=update_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Mentor updated successfully!")
            mentor = data.get('mentor', data)
            print_info(f"New name: {mentor.get('full_name')}")
            return True
        else:
            print_error(f"Failed to update mentor: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_assign_teams(access_token, mentor_id, team_ids):
    """Test POST /api/assignments"""
    print_header("Testing Assign Teams to Mentor")
    
    assignment_data = {
        "mentor_id": mentor_id,
        "team_ids": team_ids
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(
            f"{BASE_URL}/api/assignments",
            json=assignment_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"{len(team_ids)} teams assigned successfully!")
            print_info(f"Message: {data.get('message')}")
            return True
        else:
            print_error(f"Failed to assign teams: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_get_mentor_assignments(access_token, mentor_id):
    """Test GET /api/assignments/mentor/{mentor_id}"""
    print_header("Testing Get Mentor Assignments")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/assignments/mentor/{mentor_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved {data.get('total', 0)} assignments")
            
            for i, assignment in enumerate(data.get('assignments', [])[:3], 1):
                print_info(f"{i}. {assignment.get('team_name')} - {assignment.get('batch_name')}")
            
            return data.get('assignments', [])
        else:
            print_error(f"Failed to get assignments: {response.status_code}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_unassign_teams(access_token, mentor_id, team_ids):
    """Test DELETE /api/assignments"""
    print_header("Testing Unassign Teams from Mentor")
    
    assignment_data = {
        "mentor_id": mentor_id,
        "team_ids": team_ids
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.delete(
            f"{BASE_URL}/api/assignments",
            json=assignment_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"{len(team_ids)} teams unassigned successfully!")
            return True
        else:
            print_error(f"Failed to unassign teams: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_delete_mentor(access_token, mentor_id):
    """Test DELETE /api/mentors/{mentor_id}"""
    print_header("Testing Delete Mentor")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.delete(
            f"{BASE_URL}/api/mentors/{mentor_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Mentor deleted successfully!")
            print_info(f"Message: {data.get('message')}")
            return True
        else:
            print_error(f"Failed to delete mentor: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def main():
    """Run all Phase 3 mentor and assignment tests"""
    print(f"\n{BLUE}{'='*70}")
    print(f"  PHASE 3 - MENTOR & ASSIGNMENT MANAGEMENT TESTING")
    print(f"  Testing Mentor CRUD & Team Assignments")
    print(f"{'='*70}{RESET}\n")
    
    # Get authentication
    access_token = input(f"{CYAN}Enter your access token (admin only): {RESET}").strip()
    
    if not access_token:
        print_error("Access token is required")
        return
    
    # Run tests
    results = []
    
    # List mentors
    mentors = test_list_mentors(access_token)
    results.append(("List Mentors", mentors is not None))
    
    if mentors is None:
        print_warning("\nMost tests require admin role. Cannot proceed without proper authorization.")
        return
    
    # Get existing mentor ID (or use first mentor)
    mentor_id = None
    if mentors and len(mentors) > 0:
        mentor_id = mentors[0].get('id')
        print_info(f"\nUsing existing mentor: {mentors[0].get('full_name')} ({mentor_id})")
        
        # Test get mentor details
        results.append(("Get Mentor Details", test_get_mentor(access_token, mentor_id)))
        
        # Test update mentor
        results.append(("Update Mentor", test_update_mentor(access_token, mentor_id)))
    
    # Get team IDs for assignment testing
    print_info("\nTo test team assignments, we need team IDs...")
    has_teams = input(f"{CYAN}Do you have team IDs to test assignments? (y/n): {RESET}").lower()
    
    if has_teams == 'y' and mentor_id:
        team_ids_input = input(f"{CYAN}Enter team IDs (comma-separated): {RESET}").strip()
        if team_ids_input:
            team_ids = [tid.strip() for tid in team_ids_input.split(',')]
            
            # Test assign teams
            results.append(("Assign Teams", test_assign_teams(access_token, mentor_id, team_ids)))
            
            # Test get assignments
            assignments = test_get_mentor_assignments(access_token, mentor_id)
            results.append(("Get Assignments", assignments is not None))
            
            # Test unassign teams
            cleanup = input(f"\n{CYAN}Unassign test teams? (y/n): {RESET}").lower()
            if cleanup == 'y':
                results.append(("Unassign Teams", test_unassign_teams(access_token, mentor_id, team_ids)))
    
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
