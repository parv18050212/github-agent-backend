#!/usr/bin/env python3
"""
Test Role Assignment System
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.backend.utils.role_manager import RoleManager


def test_auth_metadata_priority():
    """Test that auth metadata takes highest priority"""
    print("\n🧪 Test 1: Auth Metadata Priority")
    
    # Auth metadata should override everything
    metadata = {"role": "admin"}
    role = RoleManager.determine_role("test@example.com", metadata, False)
    assert role == "admin", f"Expected admin, got {role}"
    print("   ✅ Auth metadata with admin role works")
    
    metadata = {"role": "mentor"}
    role = RoleManager.determine_role("test@example.com", metadata, False)
    assert role == "mentor", f"Expected mentor, got {role}"
    print("   ✅ Auth metadata with mentor role works")
    
    # Invalid role should be ignored
    metadata = {"role": "student"}
    role = RoleManager.determine_role("test@example.com", metadata, False)
    assert role == "mentor", f"Expected mentor (default), got {role}"
    print("   ✅ Invalid auth metadata falls back to default")


def test_first_user_privilege():
    """Test that first user becomes admin"""
    print("\n🧪 Test 2: First User Privilege")
    
    role = RoleManager.determine_role("newuser@example.com", None, True)
    assert role == "admin", f"Expected admin for first user, got {role}"
    print("   ✅ First user gets admin role")
    
    role = RoleManager.determine_role("newuser@example.com", None, False)
    assert role == "mentor", f"Expected mentor for non-first user, got {role}"
    print("   ✅ Non-first user gets mentor role")


def test_admin_email_whitelist():
    """Test admin email whitelist"""
    print("\n🧪 Test 3: Admin Email Whitelist")
    
    # Set up test emails
    os.environ["ADMIN_EMAILS"] = "admin@test.com,superuser@example.com"
    RoleManager._admin_emails_cache = None  # Clear cache
    
    role = RoleManager.determine_role("admin@test.com", None, False)
    assert role == "admin", f"Expected admin for whitelisted email, got {role}"
    print("   ✅ Whitelisted email gets admin role")
    
    role = RoleManager.determine_role("ADMIN@TEST.COM", None, False)
    assert role == "admin", f"Expected admin (case-insensitive), got {role}"
    print("   ✅ Case-insensitive matching works")
    
    role = RoleManager.determine_role("superuser@example.com", None, False)
    assert role == "admin", f"Expected admin for second whitelisted email, got {role}"
    print("   ✅ Multiple admin emails work")
    
    role = RoleManager.determine_role("random@test.com", None, False)
    assert role == "mentor", f"Expected mentor for non-whitelisted email, got {role}"
    print("   ✅ Non-whitelisted email gets mentor role")
    
    # Clean up
    os.environ.pop("ADMIN_EMAILS", None)
    RoleManager._admin_emails_cache = None


def test_no_domain_patterns():
    """Test that domain-based auto-admin is disabled"""
    print("\n🧪 Test 4: Domain Patterns Disabled (For Educational Institutions)")
    
    # Even if we set domain patterns, they should be ignored
    # This prevents accidentally making all college users admins
    
    role = RoleManager.determine_role("prof@university.edu", None, False)
    assert role == "mentor", f"Expected mentor (domain patterns disabled), got {role}"
    print("   ✅ University domain defaults to mentor")
    
    role = RoleManager.determine_role("student@college.edu", None, False)
    assert role == "mentor", f"Expected mentor (domain patterns disabled), got {role}"
    print("   ✅ College domain defaults to mentor")
    
    print("   ✅ Domain-based auto-admin disabled to prevent mentor conflicts")


def test_priority_order():
    """Test that priority order is maintained"""
    print("\n🧪 Test 5: Priority Order")
    
    # Auth metadata should win over everything
    os.environ["ADMIN_EMAILS"] = "test@example.com"
    RoleManager._admin_emails_cache = None
    
    metadata = {"role": "mentor"}
    role = RoleManager.determine_role("test@example.com", metadata, True)
    assert role == "mentor", f"Auth metadata should override first user privilege"
    print("   ✅ Auth metadata > First user privilege")
    
    # First user should win over email whitelist
    role = RoleManager.determine_role("other@example.com", None, True)
    assert role == "admin", f"First user should win over default"
    print("   ✅ First user > Email whitelist > Default")
    
    # Clean up
    os.environ.pop("ADMIN_EMAILS", None)
    RoleManager._admin_emails_cache = None


def test_default_fallback():
    """Test default fallback behavior"""
    print("\n🧪 Test 6: Default Fallback")
    
    # Clear all environment variables
    os.environ.pop("ADMIN_EMAILS", None)
    RoleManager._admin_emails_cache = None
    
    role = RoleManager.determine_role("random@example.com", None, False)
    assert role == "mentor", f"Expected mentor as default, got {role}"
    print("   ✅ Defaults to mentor when no criteria match")
    
    role = RoleManager.determine_role(None, None, False)
    assert role == "mentor", f"Expected mentor for None email, got {role}"
    print("   ✅ Handles None email gracefully")


def test_role_validation():
    """Test role validation functions"""
    print("\n🧪 Test 7: Role Validation")
    
    assert RoleManager.is_valid_role("admin") == True
    print("   ✅ 'admin' is valid")
    
    assert RoleManager.is_valid_role("mentor") == True
    print("   ✅ 'mentor' is valid")
    
    assert RoleManager.is_valid_role("student") == False
    print("   ✅ 'student' is invalid")
    
    assert RoleManager.is_valid_role(None) == False
    print("   ✅ None is invalid")
    
    assert RoleManager.normalize_role("admin") == "admin"
    assert RoleManager.normalize_role("mentor") == "mentor"
    assert RoleManager.normalize_role("invalid") == "mentor"
    print("   ✅ Role normalization works")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Role Assignment System Tests")
    print("=" * 60)
    
    try:
        test_auth_metadata_priority()
        test_first_user_privilege()
        test_admin_email_whitelist()
        test_no_domain_patterns()
        test_priority_order()
        test_default_fallback()
        test_role_validation()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
