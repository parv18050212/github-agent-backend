"""
Authentication and Authorization Middleware
Handles JWT verification, role-based access control, and user context
"""
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from uuid import UUID
import os
from supabase import Client
import jwt
from functools import wraps

from ..database import get_supabase_client, get_supabase_admin_client

# Security scheme
security = HTTPBearer()


class AuthUser:
    """Authenticated user context"""
    def __init__(self, user_id: UUID, email: str, role: str, full_name: Optional[str] = None):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.full_name = full_name
    
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role == "admin"
    
    def is_mentor(self) -> bool:
        """Check if user is mentor"""
        return self.role == "mentor"
    
    def has_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles"""
        return self.role in roles


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> AuthUser:
    """
    Verify JWT token and return current user
    Extracts user from Supabase JWT token
    """
    token = credentials.credentials
    
    try:
        supabase = get_supabase_client()
        
        # Get user from Supabase using the token
        user_response = supabase.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = user_response.user
        
        # Get user metadata (includes role)
        user_metadata = user.user_metadata or {}
        app_metadata = user.app_metadata or {}
        
        # Try to get role from metadata (app_metadata takes precedence)
        role = app_metadata.get("role") or user_metadata.get("role") or "mentor"
        
        # Get full name
        full_name = user_metadata.get("full_name") or user_metadata.get("name")
        
        return AuthUser(
            user_id=UUID(user.id),
            email=user.email,
            role=role,
            full_name=full_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security, auto_error=False)
) -> Optional[AuthUser]:
    """
    Get current user if token is provided, otherwise return None
    Used for endpoints that work both authenticated and unauthenticated
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


class RoleChecker:
    """
    Dependency to check if user has required role(s)
    Usage:
        @router.get("/admin-only", dependencies=[Depends(RoleChecker(["admin"]))])
        async def admin_endpoint():
            ...
    """
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(self.allowed_roles)}"
            )
        return user


# Convenience dependencies
require_admin = Depends(RoleChecker(["admin"]))
require_mentor = Depends(RoleChecker(["mentor", "admin"]))  # Admin can access mentor routes
require_auth = Depends(get_current_user)


async def verify_team_access(
    team_id: UUID,
    user: AuthUser = Depends(get_current_user)
) -> bool:
    """
    Verify if user has access to a specific team
    - Admins have access to all teams
    - Mentors have access to their assigned teams
    """
    if user.is_admin():
        return True
    
    if user.is_mentor():
        # Check if mentor is assigned to this team
        supabase = get_supabase_admin_client()
        
        result = supabase.table("mentor_team_assignments")\
            .select("id")\
            .eq("mentor_id", str(user.user_id))\
            .eq("team_id", str(team_id))\
            .execute()
        
        if result.data and len(result.data) > 0:
            return True
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this team"
    )


async def verify_batch_access(
    batch_id: UUID,
    user: AuthUser = Depends(get_current_user)
) -> bool:
    """
    Verify if user has access to a specific batch
    - Admins have access to all batches
    - Mentors have access to batches where they have team assignments
    """
    if user.is_admin():
        return True
    
    if user.is_mentor():
        # Check if mentor has any teams in this batch
        supabase = get_supabase_admin_client()
        
        result = supabase.table("mentor_team_assignments")\
            .select("id")\
            .eq("mentor_id", str(user.user_id))\
            .eq("batch_id", str(batch_id))\
            .execute()
        
        if result.data and len(result.data) > 0:
            return True
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this batch"
    )


def admin_only(func):
    """
    Decorator to restrict endpoint to admins only
    Usage:
        @router.get("/admin-route")
        @admin_only
        async def admin_route(user: AuthUser = Depends(get_current_user)):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user = kwargs.get("user") or kwargs.get("current_user")
        if not user or not user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return await func(*args, **kwargs)
    return wrapper


def mentor_or_admin(func):
    """
    Decorator to restrict endpoint to mentors and admins
    Usage:
        @router.get("/mentor-route")
        @mentor_or_admin
        async def mentor_route(user: AuthUser = Depends(get_current_user)):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        user = kwargs.get("user") or kwargs.get("current_user")
        if not user or not user.has_role("admin", "mentor"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mentor or admin access required"
            )
        return await func(*args, **kwargs)
    return wrapper
