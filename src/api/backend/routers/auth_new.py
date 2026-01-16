"""
Authentication Router
Handles user authentication, profile management, and role verification
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional
from uuid import UUID

from ..schemas import (
    LoginRequest,
    LoginResponse,
    UserProfileResponse,
    UserUpdateRequest,
    ErrorResponse
)
from ..middleware import get_current_user, AuthUser
from ..database import get_supabase_client, get_supabase_admin_client

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse, responses={401: {"model": ErrorResponse}})
async def login(request: LoginRequest):
    """
    Authenticate user with Google OAuth ID token
    
    **Process:**
    1. Verify Google ID token with Supabase
    2. Create/update user in database
    3. Return JWT tokens and user profile
    
    **Returns:**
    - access_token: JWT token for API requests
    - refresh_token: Token to refresh access token
    - user: User profile with role
    """
    try:
        supabase = get_supabase_client()
        
        # Sign in with ID token (Supabase handles Google verification)
        auth_response = supabase.auth.sign_in_with_id_token({
            "provider": "google",
            "token": request.id_token
        })
        
        if not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token"
            )
        
        user = auth_response.user
        session = auth_response.session
        
        # Get user metadata
        user_metadata = user.user_metadata or {}
        app_metadata = user.app_metadata or {}
        
        # Get role (default to 'mentor' if not set)
        role = app_metadata.get("role") or user_metadata.get("role") or "mentor"
        
        # Build user profile response
        user_profile = UserProfileResponse(
            id=UUID(user.id),
            email=user.email,
            role=role,
            full_name=user_metadata.get("full_name") or user_metadata.get("name"),
            avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
            created_at=user.created_at
        )
        
        return LoginResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            user=user_profile,
            expires_in=session.expires_in or 3600
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_token(refresh_token: str):
    """
    Refresh access token using refresh token
    
    **Parameters:**
    - refresh_token: Valid refresh token
    
    **Returns:**
    - New access_token and refresh_token
    """
    try:
        supabase = get_supabase_client()
        
        # Refresh session
        auth_response = supabase.auth.refresh_session(refresh_token)
        
        if not auth_response.user or not auth_response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        user = auth_response.user
        session = auth_response.session
        
        # Get user metadata
        user_metadata = user.user_metadata or {}
        app_metadata = user.app_metadata or {}
        role = app_metadata.get("role") or user_metadata.get("role") or "mentor"
        
        user_profile = UserProfileResponse(
            id=UUID(user.id),
            email=user.email,
            role=role,
            full_name=user_metadata.get("full_name") or user_metadata.get("name"),
            avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
            created_at=user.created_at
        )
        
        return LoginResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            user=user_profile,
            expires_in=session.expires_in or 3600
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(current_user: AuthUser = Depends(get_current_user)):
    """
    Get current user's profile
    
    **Requires:** Valid JWT token
    
    **Returns:** User profile with role and metadata
    """
    try:
        supabase = get_supabase_client()
        
        # Get fresh user data from Supabase
        user_response = supabase.auth.get_user()
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        user = user_response.user
        user_metadata = user.user_metadata or {}
        app_metadata = user.app_metadata or {}
        
        role = app_metadata.get("role") or user_metadata.get("role") or current_user.role
        
        return UserProfileResponse(
            id=UUID(user.id),
            email=user.email,
            role=role,
            full_name=user_metadata.get("full_name") or user_metadata.get("name") or current_user.full_name,
            avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
            created_at=user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch profile: {str(e)}"
        )


@router.put("/me", response_model=UserProfileResponse)
async def update_current_user_profile(
    update_data: UserUpdateRequest,
    current_user: AuthUser = Depends(get_current_user)
):
    """
    Update current user's profile
    
    **Requires:** Valid JWT token
    
    **Updatable fields:**
    - full_name
    - avatar_url
    
    **Note:** Email and role cannot be changed through this endpoint
    """
    try:
        supabase = get_supabase_client()
        
        # Prepare update data
        user_metadata = {}
        if update_data.full_name is not None:
            user_metadata["full_name"] = update_data.full_name
        if update_data.avatar_url is not None:
            user_metadata["avatar_url"] = update_data.avatar_url
        
        # Update user metadata
        if user_metadata:
            auth_response = supabase.auth.update_user({
                "data": user_metadata
            })
            
            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to update profile"
                )
            
            user = auth_response.user
        else:
            # No updates, just return current profile
            user_response = supabase.auth.get_user()
            user = user_response.user
        
        user_metadata = user.user_metadata or {}
        app_metadata = user.app_metadata or {}
        role = app_metadata.get("role") or user_metadata.get("role") or current_user.role
        
        return UserProfileResponse(
            id=UUID(user.id),
            email=user.email,
            role=role,
            full_name=user_metadata.get("full_name") or user_metadata.get("name"),
            avatar_url=user_metadata.get("avatar_url") or user_metadata.get("picture"),
            created_at=user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.post("/logout")
async def logout(current_user: AuthUser = Depends(get_current_user)):
    """
    Logout current user
    
    **Requires:** Valid JWT token
    
    **Effect:** Invalidates current session
    """
    try:
        supabase = get_supabase_client()
        
        # Sign out user
        supabase.auth.sign_out()
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )
