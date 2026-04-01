"""
Auth router — GitHub OAuth flow + session management.

Flow:
  GET /auth/login      → redirect to GitHub OAuth authorize URL
  GET /auth/callback   → exchange code, upsert user, set HttpOnly session cookie
  GET /auth/me         → return current user from session
  POST /auth/logout    → clear session cookie
"""
import logging
import secrets
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session

logger = logging.getLogger(__name__)
router = APIRouter()

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

COOKIE_NAME = "echelon_session"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days
_OAUTH_STATE_COOKIE = "echelon_oauth_state"
_OAUTH_STATE_MAX_AGE = 300  # 5 minutes — must complete OAuth within this window

_serializer = URLSafeTimedSerializer(settings.secret_key)


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Redirect the user to GitHub OAuth authorization."""
    # Generate CSRF state nonce to prevent OAuth flow hijacking
    state = secrets.token_urlsafe(32)
    params = f"client_id={settings.github_client_id}&scope=read:user,user:email&state={state}"
    redirect = RedirectResponse(f"{GITHUB_AUTHORIZE_URL}?{params}")
    redirect.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        max_age=_OAUTH_STATE_MAX_AGE,
        httponly=True,
        samesite="lax",  # lax required here — callback is a cross-site redirect from GitHub
        secure=_should_use_secure_cookie(request),
    )
    return redirect


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle GitHub OAuth callback.

    Exchanges code for access token, fetches GitHub user profile,
    upserts user record, and sets an HttpOnly session cookie.
    """
    # Validate CSRF state nonce
    expected_state = request.cookies.get(_OAUTH_STATE_COOKIE)
    if not expected_state or not secrets.compare_digest(expected_state, state):
        logger.warning("GitHub OAuth: state mismatch — possible CSRF")
        raise HTTPException(403, "OAuth state validation failed")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

        access_token = token_data.get("access_token")
        if not access_token:
            logger.error("GitHub OAuth: no access_token in response")
            return RedirectResponse("/?auth_error=token_failed")

        # Fetch user profile
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        user_resp.raise_for_status()
        gh_user = user_resp.json()

    github_id = gh_user["id"]
    github_username = gh_user.get("login", "")
    # Do not log email per guardrails
    email = gh_user.get("email")

    # Upsert user record
    result = await session.execute(
        text("""
            INSERT INTO users (id, github_id, github_username, email, created_at, last_seen_at)
            VALUES (:id, :github_id, :username, :email, NOW(), NOW())
            ON CONFLICT (github_id) DO UPDATE SET
                github_username = EXCLUDED.github_username,
                email = EXCLUDED.email,
                last_seen_at = NOW()
            RETURNING id
        """),
        {
            "id": str(uuid.uuid4()),
            "github_id": github_id,
            "username": github_username,
            "email": email,
        },
    )
    user_id = str(result.scalar_one())
    await session.commit()

    logger.info("GitHub OAuth: user authenticated (github_id=%d)", github_id)

    # Create signed session token
    session_token = _serializer.dumps({"user_id": user_id})

    # Set HttpOnly cookie and redirect to frontend
    redirect = RedirectResponse("/")
    redirect.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="strict",
        secure=_should_use_secure_cookie(request),
    )
    # Clear the OAuth state cookie — no longer needed
    redirect.delete_cookie(_OAUTH_STATE_COOKIE)
    return redirect


@router.get("/me")
async def get_me(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict | None:
    """Return the current authenticated user, or null if anonymous."""
    user_id = _get_user_id_from_cookie(request)
    if not user_id:
        return None

    result = await session.execute(
        text("SELECT id, github_username, email, byok_key_enc IS NOT NULL as has_byok FROM users WHERE id = :id"),
        {"id": user_id},
    )
    row = result.fetchone()
    if not row:
        return None

    return {
        "id": str(row.id),
        "githubUsername": row.github_username,
        "email": row.email,
        "byokStorageMode": "server" if row.has_byok else "browser",
    }


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


def _get_user_id_from_cookie(request: Request) -> str | None:
    """Extract and validate the user_id from the session cookie.

    Args:
        request: FastAPI request.

    Returns:
        User ID string, or None if no valid session.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=COOKIE_MAX_AGE)
        return data.get("user_id")
    except BadSignature:
        return None


def get_current_user_id(request: Request) -> str | None:
    """FastAPI dependency to get the current user ID from session cookie.

    Returns None for anonymous users (read endpoints still work).
    Use require_auth() for write endpoints.
    """
    return _get_user_id_from_cookie(request)


def _should_use_secure_cookie(request: Request) -> bool:
    """Keep secure cookies in production while allowing local HTTP auth."""
    host = (request.url.hostname or "").lower()
    return host not in {"localhost", "127.0.0.1", "::1"}


def require_auth(request: Request) -> str:
    """FastAPI dependency that requires authentication.

    Raises HTTPException 401 if not authenticated.
    """
    user_id = _get_user_id_from_cookie(request)
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id
