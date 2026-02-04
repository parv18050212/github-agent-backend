"""
Phase 1 Testing Script
Tests authentication and batch management endpoints
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BLUE = '\033[94m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_error(text):
    print(f"{RED}✗ {text}{RESET}")

def print_info(text):
    print(f"{YELLOW}ℹ {text}{RESET}")


def test_health():
    """Test health endpoint"""
    print_header("Testing Health Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print_success(f"Health check passed: {data['status']}")
            print_info(f"Database: {data.get('database', 'N/A')}")
            return True
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Health check error: {str(e)}")
        return False


def test_root():
    """Test root endpoint"""
    print_header("Testing Root Endpoint")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            print_success(f"API Name: {data['name']}")
            print_success(f"Version: {data['version']}")
            print_success(f"Status: {data['status']}")
            return True
        else:
            print_error(f"Root endpoint failed: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Root endpoint error: {str(e)}")
        return False


def test_batch_create_without_auth():
    """Test batch creation without authentication (should fail)"""
    print_header("Testing Batch Creation (No Auth - Should Fail)")
    
    batch_data = {
        "name": "Test Batch 2024",
        "semester": "4th Sem",
        "year": 2024,
        "start_date": "2024-01-01T00:00:00Z",
        "end_date": "2024-06-30T23:59:59Z"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/batches", json=batch_data)
        if response.status_code == 401 or response.status_code == 403:
            print_success("Correctly rejected unauthenticated request")
            return True
        else:
            print_error(f"Expected 401/403, got {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Test error: {str(e)}")
        return False


def test_batch_list_without_auth():
    """Test batch listing without authentication"""
    print_header("Testing Batch List (No Auth)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/batches")
        if response.status_code == 401:
            print_info("Batch list requires authentication")
            return True
        elif response.status_code == 200:
            data = response.json()
            print_success(f"Batch list accessible without auth")
            print_info(f"Total batches: {data.get('total', 0)}")
            if data.get('batches'):
                for batch in data['batches']:
                    print_info(f"  - {batch['name']} ({batch['year']})")
            return True
        else:
            print_error(f"Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Test error: {str(e)}")
        return False


def test_auth_me_without_token():
    """Test /api/auth/me without token (should fail)"""
    print_header("Testing Auth /me Endpoint (No Token - Should Fail)")
    
    try:
        response = requests.get(f"{BASE_URL}/api/auth/me")
        if response.status_code == 401 or response.status_code == 403:
            print_success("Correctly rejected request without token")
            return True
        else:
            print_error(f"Expected 401/403, got {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Test error: {str(e)}")
        return False


def test_documentation():
    """Test Swagger documentation"""
    print_header("Testing API Documentation")
    
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code == 200:
            print_success("Swagger UI accessible at /docs")
            return True
        else:
            print_error(f"Docs not accessible: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Docs error: {str(e)}")
        return False


def test_openapi_schema():
    """Test OpenAPI schema"""
    print_header("Testing OpenAPI Schema")
    
    try:
        response = requests.get(f"{BASE_URL}/openapi.json")
        if response.status_code == 200:
            schema = response.json()
            print_success(f"OpenAPI schema available")
            print_info(f"Title: {schema.get('info', {}).get('title')}")
            print_info(f"Version: {schema.get('info', {}).get('version')}")
            
            # Count endpoints
            paths = schema.get('paths', {})
            auth_endpoints = [p for p in paths if '/api/auth' in p]
            batch_endpoints = [p for p in paths if '/api/batches' in p]
            
            print_info(f"Total endpoints: {len(paths)}")
            print_info(f"Auth endpoints: {len(auth_endpoints)}")
            print_info(f"Batch endpoints: {len(batch_endpoints)}")
            
            # List new endpoints
            print("\n  New Auth Endpoints:")
            for endpoint in auth_endpoints:
                print(f"    {endpoint}")
            
            print("\n  New Batch Endpoints:")
            for endpoint in batch_endpoints:
                print(f"    {endpoint}")
            
            return True
        else:
            print_error(f"Schema not accessible: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Schema error: {str(e)}")
        return False


def main():
    """Run all Phase 1 tests"""
    print(f"\n{BLUE}{'='*60}")
    print(f"  PHASE 1 IMPLEMENTATION TESTING")
    print(f"  Testing Authentication & Batch Management")
    print(f"{'='*60}{RESET}\n")
    
    results = []
    
    # Basic connectivity tests
    results.append(("Health Check", test_health()))
    results.append(("Root Endpoint", test_root()))
    results.append(("API Documentation", test_documentation()))
    results.append(("OpenAPI Schema", test_openapi_schema()))
    
    # Authentication tests (without actual Google token)
    results.append(("Auth Protection", test_auth_me_without_token()))
    
    # Batch management tests (without authentication)
    results.append(("Batch Create Auth Check", test_batch_create_without_auth()))
    results.append(("Batch List Access", test_batch_list_without_auth()))
    
    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {name:.<40} {status}")
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    if passed == total:
        print(f"{GREEN}All {total} tests passed! ✓{RESET}")
    else:
        print(f"{YELLOW}{passed}/{total} tests passed{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    # Next steps
    print_header("Next Steps for Full Testing")
    print_info("To test authenticated endpoints, you need:")
    print("  1. Configure Google OAuth in Supabase")
    print("  2. Obtain a valid Google ID token")
    print("  3. Use POST /api/auth/login with the ID token")
    print("  4. Use returned access_token for authenticated requests")
    print("\n  Example with token:")
    print("    headers = {'Authorization': 'Bearer YOUR_ACCESS_TOKEN'}")
    print("    requests.post('/api/batches', json=data, headers=headers)")
    
    print_info("\nManual testing available at:")
    print(f"  Swagger UI: {BASE_URL}/docs")
    print(f"  ReDoc: {BASE_URL}/redoc")
    
    print("\n")


if __name__ == "__main__":
    main()
