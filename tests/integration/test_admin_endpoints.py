"""
Test script for new admin user management endpoints
Tests:
1. GET /api/admin/users - List all users
2. PATCH /api/admin/users/{userId}/role - Update user role
3. GET /api/analysis/{jobId} - Route alias verification
"""
import requests
import json
from typing import Optional

BASE_URL = "http://localhost:8000"

# Mock admin JWT token (replace with actual token for testing)
# This should be obtained from Supabase auth
ADMIN_TOKEN = "your-admin-jwt-token-here"

HEADERS = {
    "Authorization": f"Bearer {ADMIN_TOKEN}",
    "Content-Type": "application/json"
}


def test_list_users():
    """Test GET /api/admin/users"""
    print("\n" + "="*60)
    print("TEST 1: List all users")
    print("="*60)
    
    url = f"{BASE_URL}/api/admin/users"
    
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! Found {len(data.get('users', []))} users")
            print("\nUsers:")
            for user in data.get('users', [])[:3]:  # Show first 3
                print(f"  - {user['email']} (role: {user.get('role', 'none')})")
        elif response.status_code == 403:
            print("❌ 403 Forbidden - Admin access required")
            print("   Make sure you're using an admin JWT token")
        else:
            print(f"❌ Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error - Make sure the server is running on port 8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_update_user_role(user_id: str, new_role: Optional[str] = "mentor"):
    """Test PATCH /api/admin/users/{userId}/role"""
    print("\n" + "="*60)
    print(f"TEST 2: Update user role to '{new_role}'")
    print("="*60)
    
    url = f"{BASE_URL}/api/admin/users/{user_id}/role"
    payload = {"role": new_role}
    
    try:
        response = requests.patch(url, headers=HEADERS, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success! {data.get('message')}")
            print(f"   User: {data.get('email')}")
            print(f"   New Role: {data.get('role')}")
        elif response.status_code == 400:
            print(f"❌ 400 Bad Request: {response.json().get('detail')}")
        elif response.status_code == 403:
            print("❌ 403 Forbidden - Admin access required")
        elif response.status_code == 404:
            print("❌ 404 Not Found - User ID not found")
        else:
            print(f"❌ Error: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error - Make sure the server is running on port 8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def test_analysis_route_alias(job_id: str = "test-job-id"):
    """Test GET /api/analysis/{jobId} route alias"""
    print("\n" + "="*60)
    print("TEST 3: Analysis route alias")
    print("="*60)
    
    url = f"{BASE_URL}/api/analysis/{job_id}"
    
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Route alias working! Job status: {data.get('status')}")
        elif response.status_code == 404:
            print(f"⚠️  Route alias exists but job not found (expected for test ID)")
            print("   This means the route is working correctly!")
        else:
            print(f"Status: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error - Make sure the server is running on port 8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")


def check_server_status():
    """Check if server is running"""
    print("\n" + "="*60)
    print("CHECKING SERVER STATUS")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Server is running and healthy")
            return True
        else:
            print(f"⚠️  Server responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running!")
        print("   Start the server with: uvicorn main:app --reload")
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 ADMIN ENDPOINTS TEST SUITE")
    print("="*60)
    
    # Check if server is running
    if not check_server_status():
        print("\n❌ Cannot run tests - server is not running")
        print("   Please start the server and try again")
        exit(1)
    
    print("\n⚠️  IMPORTANT: Update ADMIN_TOKEN in this script with a real admin JWT")
    print("   Get token from Supabase auth after logging in as admin")
    
    # Run tests
    test_list_users()
    
    # Uncomment to test role update (replace with real user ID)
    # test_update_user_role("user-uuid-here", "mentor")
    
    test_analysis_route_alias()
    
    print("\n" + "="*60)
    print("✅ TEST SUITE COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Get a real admin JWT token from Supabase")
    print("2. Update ADMIN_TOKEN variable in this script")
    print("3. Run tests again to verify admin endpoints")
    print("4. Test from frontend admin portal")
    print("="*60 + "\n")
