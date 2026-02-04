"""
Real Authentication Testing Script
Tests all Phase 1 endpoints with actual Google OAuth tokens
"""
import requests
import json
from datetime import datetime, timedelta
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


def get_token_from_user():
    """Get authentication token from user"""
    print_header("Authentication Setup")
    
    print_info("You can test with either:")
    print("  1. Supabase Access Token (from get_token.html) - RECOMMENDED")
    print("  2. Google ID token (for testing login flow)")
    print("  3. Skip authentication tests\n")
    
    choice = input(f"{CYAN}What do you have? (access/google/skip): {RESET}").lower()
    
    if choice == 'skip':
        return None, "skip", None
    elif choice == 'access':
        access_token = input(f"{CYAN}Enter your Supabase access token: {RESET}").strip()
        print_info("Using existing Supabase token - will skip login test")
        return access_token, "access_token", None
    elif choice == 'google':
        id_token = input(f"{CYAN}Enter your Google ID token: {RESET}").strip()
        return id_token, "id_token", None
    else:
        print_warning("\nWithout a token, we can only test unauthenticated endpoints.")
        return None, "no_token", None


def login_with_google(id_token):
    """Login using Google ID token"""
    print_header("Testing Login with Google OAuth")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"id_token": id_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Login successful!")
            print_info(f"User: {data['user']['email']}")
            print_info(f"Role: {data['user']['role']}")
            print_info(f"Access Token: {data['access_token'][:50]}...")
            print_info(f"Expires in: {data['expires_in']} seconds")
            
            return {
                'access_token': data['access_token'],
                'refresh_token': data['refresh_token'],
                'user': data['user']
            }
        else:
            print_error(f"Login failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Login error: {str(e)}")
        return None


def test_get_profile(access_token):
    """Test GET /api/auth/me"""
    print_header("Testing Get Current User Profile")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Profile retrieved successfully!")
            print_info(f"ID: {data['id']}")
            print_info(f"Email: {data['email']}")
            print_info(f"Role: {data['role']}")
            print_info(f"Full Name: {data.get('full_name', 'Not set')}")
            return True
        else:
            print_error(f"Failed to get profile: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_update_profile(access_token):
    """Test PUT /api/auth/me"""
    print_header("Testing Update User Profile")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        update_data = {
            "full_name": f"Test User - {datetime.now().strftime('%H:%M:%S')}"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/auth/me",
            json=update_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Profile updated successfully!")
            print_info(f"New full name: {data['full_name']}")
            return True
        else:
            print_error(f"Failed to update profile: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_create_batch(access_token, user_role):
    """Test POST /api/batches"""
    print_header("Testing Create Batch")
    
    if user_role != 'admin':
        print_warning(f"Your role is '{user_role}', not 'admin'. This will likely fail.")
        print_info("Only admins can create batches.")
    
    batch_data = {
        "name": f"Test Batch {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "semester": "Test Semester",
        "year": 2024,
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-12-31T23:59:59Z"
    }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(
            f"{BASE_URL}/api/batches",
            json=batch_data,
            headers=headers
        )
        
        if response.status_code == 201:
            data = response.json()
            print_success("Batch created successfully!")
            print_info(f"ID: {data['id']}")
            print_info(f"Name: {data['name']}")
            print_info(f"Semester: {data['semester']} {data['year']}")
            print_info(f"Status: {data['status']}")
            return data['id']
        elif response.status_code == 403:
            print_warning("Access denied - Admin role required")
            print_info("Your account needs admin privileges to create batches")
            return None
        else:
            print_error(f"Failed to create batch: {response.status_code}")
            print_error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_list_batches(access_token):
    """Test GET /api/batches"""
    print_header("Testing List Batches")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{BASE_URL}/api/batches", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"Retrieved {data['total']} batches")
            
            for i, batch in enumerate(data['batches'][:5], 1):
                print_info(f"{i}. {batch['name']} - {batch['status']}")
                print(f"   Year: {batch['year']}, Teams: {batch['team_count']}, Students: {batch['student_count']}")
            
            if data['total'] > 5:
                print_info(f"... and {data['total'] - 5} more")
            
            return data['batches']
        else:
            print_error(f"Failed to list batches: {response.status_code}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_get_batch(access_token, batch_id):
    """Test GET /api/batches/{batch_id}"""
    print_header("Testing Get Batch Details")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            f"{BASE_URL}/api/batches/{batch_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Batch details retrieved!")
            print_info(f"Name: {data['name']}")
            print_info(f"Semester: {data['semester']} {data['year']}")
            print_info(f"Status: {data['status']}")
            print_info(f"Teams: {data['team_count']}")
            print_info(f"Students: {data['student_count']}")
            print_info(f"Avg Score: {data.get('avg_score', 'N/A')}")
            print_info(f"Completed Projects: {data['completed_projects']}")
            print_info(f"At-Risk Teams: {data['at_risk_teams']}")
            return True
        else:
            print_error(f"Failed to get batch: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def test_refresh_token(refresh_token):
    """Test POST /api/auth/refresh"""
    print_header("Testing Token Refresh")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Token refreshed successfully!")
            print_info(f"New Access Token: {data['access_token'][:50]}...")
            return data['access_token']
        else:
            print_error(f"Failed to refresh token: {response.status_code}")
            return None
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return None


def test_logout(access_token):
    """Test POST /api/auth/logout"""
    print_header("Testing Logout")
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(f"{BASE_URL}/api/auth/logout", headers=headers)
        
        if response.status_code == 200:
            print_success("Logout successful!")
            return True
        else:
            print_error(f"Logout failed: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"Error: {str(e)}")
        return False


def main():
    """Run all authenticated tests"""
    print(f"\n{BLUE}{'='*70}")
    print(f"  PHASE 1 - REAL AUTHENTICATION TESTING")
    print(f"  Testing with Google OAuth Tokens")
    print(f"{'='*70}{RESET}\n")
    
    # Get authentication
    access_token, token_type, refresh_token = get_token_from_user()
    
    if token_type == "skip":
        print_warning("\nSkipping authentication tests.")
        print_info("Run basic tests with: python test_phase1.py")
        return
    
    if token_type == "no_token":
        print_warning("\nCannot test authenticated endpoints without a token.")
        print_info("\nSee: http://localhost:8000/docs for manual testing")
        return
    
    # If user provided Google ID token, login first
    if token_type == "id_token":
        auth_data = login_with_google(access_token)
        if not auth_data:
            print_error("\nLogin failed. Cannot continue with authenticated tests.")
            return
        
        access_token = auth_data['access_token']
        refresh_token = auth_data['refresh_token']
        user_role = auth_data['user']['role']
    else:
        # User provided Supabase access token, verify it works
        print_header("Verifying Access Token")
        print_info("Testing if the provided token is valid...")
        
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                print_success("Token is valid!")
                print_info(f"Logged in as: {data['email']}")
                user_role = data['role']
                print_info(f"Role: {user_role}")
                refresh_token = None  # We don't have refresh token in this case
            else:
                print_error(f"Token validation failed: {response.status_code}")
                print_error(f"Response: {response.text}")
                print_warning("\nThe token may be expired or invalid.")
                print_info("Please get a new token from get_token.html")
                return
        except Exception as e:
            print_error(f"Error validating token: {str(e)}")
            return
    
    # Run tests
    results = []
    
    # Auth endpoints (skip login if using access token)
    if token_type == "id_token":
        results.append(("Login with Google", True))  # Already passed above
    
    results.append(("Get Profile", test_get_profile(access_token)))
    results.append(("Update Profile", test_update_profile(access_token)))
    
    # Batch management
    results.append(("List Batches", test_list_batches(access_token) is not None))
    
    batch_id = test_create_batch(access_token, user_role)
    if batch_id:
        results.append(("Create Batch", True))
        results.append(("Get Batch Details", test_get_batch(access_token, batch_id)))
    else:
        results.append(("Create Batch", False))
        # Try with first batch from list
        batches = test_list_batches(access_token)
        if batches and len(batches) > 0:
            results.append(("Get Batch Details", test_get_batch(access_token, batches[0]['id'])))
    
    # Token management (only if we have refresh token)
    if refresh_token:
        new_token = test_refresh_token(refresh_token)
        results.append(("Refresh Token", new_token is not None))
        logout_token = new_token if new_token else access_token
    else:
        print_info("\nSkipping token refresh test (no refresh token available)")
        logout_token = access_token
    
    # Logout
    results.append(("Logout", test_logout(logout_token)))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {name:.<50} {status}")
    
    print(f"\n{BLUE}{'='*70}{RESET}")
    if passed == total:
        print(f"{GREEN}All {total} authenticated tests passed! ✓{RESET}")
    else:
        print(f"{YELLOW}{passed}/{total} tests passed{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")
    
    # Notes
    if user_role != 'admin':
        print_header("Note About Admin Access")
        print_warning(f"Your current role is: {user_role}")
        print_info("To test admin endpoints (create/update/delete batches):")
        print("  You need to set your role to 'admin' in Supabase")
        print("  Run this SQL in Supabase SQL Editor:")
        print(f"\n  {CYAN}UPDATE auth.users{RESET}")
        print(f"  {CYAN}SET raw_app_meta_data = raw_app_meta_data || '{json.dumps({'role': 'admin'})}'::jsonb{RESET}")
        print(f"  {CYAN}WHERE email = 'your@email.com';{RESET}\n")


if __name__ == "__main__":
    main()
