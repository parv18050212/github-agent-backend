"""
Authentication and authorization helpers for Supabase JWT tokens.
"""
from typing import Optional, Callable, Dict, Any
from fastapi import Header, HTTPException, status, Depends

from src.api.backend.database import get_supabase_client
from src.api.backend.crud import UserCRUD


class AuthContext(Dict[str, Any]):
    """Simple container for authenticated user context."""


async def get_current_user(
    authorization: Optional[str] = Header(None, convert_underscores=False)
) -> AuthContext:
    """
    Resolve the Supabase user from the Bearer token and ensure a profile exists
    in public.users. Returns a dict with user_id, email, and role.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    supabase = get_supabase_client()

    try:
        auth_resp = supabase.auth.get_user(token)
        user = getattr(auth_resp, "user", None)
    except Exception as exc:  # pragma: no cover - depends on supabase auth implementation
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}")

    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token: no user payload")

    user_id = getattr(user, "id", None)
    email = getattr(user, "email", None)
    full_name = None
    if hasattr(user, "user_metadata"):
        metadata = (getattr(user, "user_metadata", {}) or {})
        full_name = (
            metadata.get("full_name")
            or metadata.get("fullName")
            or metadata.get("name")
        )
        if not full_name:
            given = metadata.get("given_name") or metadata.get("first_name")
            family = metadata.get("family_name") or metadata.get("last_name")
            if given or family:
                full_name = " ".join([n for n in [given, family] if n])

    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token: missing user id")

    profile = UserCRUD.get_or_create_user(user_id, email=email, full_name=full_name)
    role = profile.get("role", "student") if profile else "student"

    return AuthContext({"user_id": user_id, "email": email, "role": role, "profile": profile})


def require_role(*allowed_roles: str) -> Callable[[AuthContext], AuthContext]:
    """
    Dependency factory to enforce role-based access on endpoints.
    Usage: Depends(require_role("admin", "mentor"))
    """

    async def dependency(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        role = ctx.get("role")
        if role not in allowed_roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return ctx

    return dependency
