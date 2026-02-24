import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from openclaw_api.config import settings
from openclaw_api.deps import get_db, get_redis
from openclaw_api.models import Box, BoxStatus, Customer
from openclaw_api.schemas import MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


def _create_jwt(customer_id: str, email: str) -> str:
    payload = {
        "sub": customer_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def _find_or_create_customer(
    db: AsyncSession,
    *,
    auth_provider: str,
    auth_provider_id: str,
    email: str,
    name: str | None,
    avatar_url: str | None,
) -> Customer:
    # 1. Lookup by (auth_provider, auth_provider_id)
    result = await db.execute(
        select(Customer).where(
            Customer.auth_provider == auth_provider,
            Customer.auth_provider_id == auth_provider_id,
        )
    )
    customer = result.scalar_one_or_none()
    if customer:
        customer.name = name
        customer.avatar_url = avatar_url
        await db.flush()
        return customer

    # 2. Lookup by email
    result = await db.execute(select(Customer).where(Customer.email == email))
    customer = result.scalar_one_or_none()
    if customer:
        customer.auth_provider = auth_provider
        customer.auth_provider_id = auth_provider_id
        customer.name = name
        customer.avatar_url = avatar_url
        await db.flush()
        return customer

    # 3. Create new
    customer = Customer(
        email=email,
        name=name,
        avatar_url=avatar_url,
        auth_provider=auth_provider,
        auth_provider_id=auth_provider_id,
    )
    db.add(customer)
    await db.flush()
    return customer


# --- Google OAuth ---


@router.get("/google")
async def google_login(request: Request, r: aioredis.Redis = Depends(get_redis)):
    state = secrets.token_urlsafe(32)
    await r.set(f"oauth_state:{state}", "google", ex=600)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{request.base_url}auth/callback/google",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{GOOGLE_AUTHORIZE_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return RedirectResponse(url)


@router.get("/callback/google")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    stored = await r.get(f"oauth_state:{state}")
    if stored != "google":
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    await r.delete(f"oauth_state:{state}")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{request.base_url}auth/callback/google",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")
        token_data = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")
        userinfo = userinfo_resp.json()

    customer = await _find_or_create_customer(
        db,
        auth_provider="google",
        auth_provider_id=str(userinfo["id"]),
        email=userinfo["email"],
        name=userinfo.get("name"),
        avatar_url=userinfo.get("picture"),
    )
    await db.commit()
    await db.refresh(customer)

    token = _create_jwt(customer.id, customer.email)
    return RedirectResponse(f"{settings.web_url}/auth/callback?token={token}")


# --- GitHub OAuth ---


@router.get("/github")
async def github_login(r: aioredis.Redis = Depends(get_redis)):
    state = secrets.token_urlsafe(32)
    await r.set(f"oauth_state:{state}", "github", ex=600)
    params = {
        "client_id": settings.github_client_id,
        "scope": "user:email",
        "state": state,
    }
    url = f"{GITHUB_AUTHORIZE_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    return RedirectResponse(url)


@router.get("/callback/github")
async def github_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    stored = await r.get(f"oauth_state:{state}")
    if stored != "github":
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    await r.delete(f"oauth_state:{state}")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for token")
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token returned")

        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

        user_resp = await client.get(GITHUB_USER_URL, headers=headers)
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub user")
        user_data = user_resp.json()

        emails_resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
        if emails_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch GitHub emails")
        emails_data = emails_resp.json()

    primary_email = next(
        (e["email"] for e in emails_data if e.get("primary") and e.get("verified")),
        next((e["email"] for e in emails_data if e.get("verified")), None),
    )
    if not primary_email:
        raise HTTPException(status_code=400, detail="No verified email found on GitHub account")

    customer = await _find_or_create_customer(
        db,
        auth_provider="github",
        auth_provider_id=str(user_data["id"]),
        email=primary_email,
        name=user_data.get("name") or user_data.get("login"),
        avatar_url=user_data.get("avatar_url"),
    )
    await db.commit()
    await db.refresh(customer)

    token = _create_jwt(customer.id, customer.email)
    return RedirectResponse(f"{settings.web_url}/auth/callback?token={token}")


# --- Dev login ---


@router.get("/dev-login")
async def dev_login(
    db: AsyncSession = Depends(get_db),
):
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="Not Found")

    customer = await _find_or_create_customer(
        db,
        auth_provider="dev",
        auth_provider_id="dev",
        email="dev@openclaw.dev",
        name="Dev User",
        avatar_url=None,
    )
    await db.commit()
    await db.refresh(customer)

    token = _create_jwt(customer.id, customer.email)
    return RedirectResponse(f"{settings.web_url}/auth/callback?token={token}")


# --- Me endpoint ---


@router.get("/me", response_model=MeResponse)
async def get_me(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        customer_id = payload["sub"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=401, detail="Customer not found")

    box_result = await db.execute(
        select(Box.id)
        .where(Box.customer_id == customer_id)
        .where(Box.status != BoxStatus.destroyed)
        .limit(1)
    )
    has_box = box_result.scalar_one_or_none() is not None

    return MeResponse(
        id=customer.id,
        email=customer.email,
        name=customer.name,
        avatar_url=customer.avatar_url,
        has_box=has_box,
    )
