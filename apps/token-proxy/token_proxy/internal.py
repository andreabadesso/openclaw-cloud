from __future__ import annotations

import secrets
import uuid

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from token_proxy.auth import TOKEN_CACHE_PREFIX
from token_proxy.config import settings

router = APIRouter(prefix="/internal")


def _verify_internal_key(x_internal_key: str = Header(...)) -> None:
    if not settings.internal_api_key or x_internal_key != settings.internal_api_key:
        raise HTTPException(status_code=403, detail="Invalid internal API key")


class CreateTokenRequest(BaseModel):
    customer_id: str
    box_id: str


class CreateTokenResponse(BaseModel):
    token_id: str
    token: str


@router.post("/tokens", response_model=CreateTokenResponse)
async def create_token(
    body: CreateTokenRequest,
    request: Request,
    _: None = Depends(_verify_internal_key),
) -> CreateTokenResponse:
    """Register a new proxy token for a customer's box."""
    db: AsyncSession = request.state.db
    redis: Redis = request.app.state.redis

    # Generate a random 32-char token
    raw_token = secrets.token_hex(16)  # 32 hex chars
    token_hash = bcrypt.hashpw(raw_token.encode(), bcrypt.gensalt()).decode()
    token_id = str(uuid.uuid4())

    await db.execute(
        text(
            "INSERT INTO proxy_tokens (id, customer_id, box_id, token_hash) "
            "VALUES (:id, :customer_id, :box_id, :token_hash)"
        ),
        {
            "id": token_id,
            "customer_id": body.customer_id,
            "box_id": body.box_id,
            "token_hash": token_hash,
        },
    )
    await db.commit()

    # Pre-populate cache
    import json

    await redis.set(
        f"{TOKEN_CACHE_PREFIX}{raw_token}",
        json.dumps({"customer_id": body.customer_id, "token_id": token_id}),
        ex=300,
    )

    return CreateTokenResponse(token_id=token_id, token=raw_token)


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    request: Request,
    _: None = Depends(_verify_internal_key),
) -> dict:
    """Revoke a proxy token."""
    db: AsyncSession = request.state.db

    result = await db.execute(
        text(
            "UPDATE proxy_tokens SET revoked_at = now() "
            "WHERE id = :id AND revoked_at IS NULL "
            "RETURNING customer_id"
        ),
        {"id": token_id},
    )
    row = result.fetchone()
    await db.commit()

    if row is None:
        raise HTTPException(status_code=404, detail="Token not found or already revoked")

    return {"status": "revoked", "token_id": token_id}


class UsageResponse(BaseModel):
    customer_id: str
    tokens_used: int
    tokens_limit: int
    period_start: str
    period_end: str


@router.get("/tokens/{customer_id}/usage", response_model=UsageResponse)
async def get_usage(
    customer_id: str,
    request: Request,
    _: None = Depends(_verify_internal_key),
) -> UsageResponse:
    """Get current usage for a customer."""
    db: AsyncSession = request.state.db

    result = await db.execute(
        text(
            "SELECT tokens_used, tokens_limit, period_start, period_end "
            "FROM usage_monthly "
            "WHERE customer_id = :cid "
            "  AND period_start <= now() "
            "  AND period_end > now() "
            "ORDER BY period_start DESC LIMIT 1"
        ),
        {"cid": customer_id},
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="No usage record found")

    return UsageResponse(
        customer_id=customer_id,
        tokens_used=int(row[0]),
        tokens_limit=int(row[1]),
        period_start=str(row[2]),
        period_end=str(row[3]),
    )
