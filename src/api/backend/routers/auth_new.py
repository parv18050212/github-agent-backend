"""
Authentication Router
Handles user authentication, profile management, and role verification
"""
from fastapi import APIRouter, HTTPException, Depends, status
from datetime import datetime, timezone
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
        
        # Get role (do not default to mentor for existing revoked users)
        role = app_metadata.get("role") or user_metadata.get("role")
        
        admin_client = get_supabase_admin_client()

        # Ensure users table is synced on login
        try:
            user_id = str(user.id)
            existing_user = admin_client.table("users").select("id, role, is_mentor").eq("id", user_id).limit(1).execute()
            existing_record = existing_user.data[0] if existing_user.data else None

            existing_role = existing_record.get("role") if existing_record else None
            desired_role = role if role else (existing_role if existing_record else "mentor")
            if existing_record and existing_role == "admin":
                desired_role = "admin"

            role = desired_role
            desired_is_mentor = bool(app_metadata.get("is_mentor"))
            if role == "mentor":
                desired_is_mentor = True
            if existing_record and existing_record.get("is_mentor") is True:
                desired_is_mentor = True

            profile_full_name = user_metadata.get("full_name") or user_metadata.get("name")
            now_iso = datetime.utcnow().isoformat()

            if existing_record:
                update_fields = {
                    "is_mentor": desired_is_mentor,
                    "updated_at": now_iso
                }
                if role is not None and existing_role != role:
                    update_fields["role"] = role
                if profile_full_name:
                    update_fields["full_name"] = profile_full_name
                admin_client.table("users").update(update_fields).eq("id", user_id).execute()
            else:
                admin_client.table("users").insert({
                    "id": user_id,
                    "email": user.email,
                    "full_name": profile_full_name,
                    "role": desired_role,
                    "is_mentor": desired_is_mentor,
                    "status": "active",
                    "created_at": user.created_at or now_iso
                }).execute()
        except Exception as sync_error:
            print(f"[Auth] Failed to sync users table: {sync_error}")

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
    
    **Returns:** User profile with FRESH role from Supabase Admin API (cached for 5 minutes)
    """
    from ..database import get_supabase_admin_client
    from ..utils.cache import cache, RedisCache
    
    user_id = str(current_user.user_id)
    admin_client = get_supabase_admin_client()
    
    # Check cache first
    cache_key = f"auth:role:{user_id}"
    cached_role = cache.get(cache_key)
    fresh_metadata = {}
    admin_user_created_at = None
    admin_user_avatar = None

    # Always try to fetch admin user metadata (needed for is_mentor)
    try:
        admin_user = admin_client.auth.admin.get_user_by_id(user_id)

        if admin_user and admin_user.user:
            fresh_metadata = admin_user.user.app_metadata or {}
            admin_user_created_at = admin_user.user.created_at
            user_metadata = admin_user.user.user_metadata or {}
            admin_user_avatar = user_metadata.get("avatar_url") or user_metadata.get("picture")
        else:
            print(f"[Auth] No admin user data for {user_id}")
    except Exception as e:
        print(f"[Auth] Admin API error: {e}")

    if cached_role:
        # Use cached role
        role = cached_role
    else:
        # Cache miss - fetch fresh role from Admin API
        role = fresh_metadata.get("role") or current_user.role or "mentor"
        print(f"[Auth] Fresh role from Admin API: {role} (app_metadata: {fresh_metadata})")

        # Cache the role for 5 minutes
        cache.set(cache_key, role, RedisCache.TTL_MEDIUM)
    
    print(f"[Auth] Final role for {current_user.email}: {role}")
    
    # Check if user has mentor access (app_metadata.is_mentor OR users.is_mentor OR mentors table)
    is_mentor = bool(fresh_metadata.get("is_mentor"))
    try:
        if not is_mentor:
            mentor_flag = admin_client.table("users").select("is_mentor").eq("id", user_id).limit(1).execute()
            if mentor_flag.data:
                is_mentor = bool(mentor_flag.data[0].get("is_mentor"))
        if not is_mentor:
            mentor_result = admin_client.table("mentors").select("id").eq("user_id", user_id).limit(1).execute()
            is_mentor = bool(mentor_result.data)
    except Exception as e:
        print(f"[Auth] Mentor lookup error: {e}")

    return UserProfileResponse(
        id=current_user.user_id,
        email=current_user.email,
        role=role,
        full_name=current_user.full_name,
        avatar_url=admin_user_avatar,
        created_at=admin_user_created_at or datetime.now(timezone.utc),
        is_mentor=is_mentor
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
