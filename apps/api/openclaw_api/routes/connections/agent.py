import secrets

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.config import settings
from openclaw_api.deps import get_db, get_redis
from openclaw_api.models import CustomerConnection
from openclaw_api.schemas import ConnectLinkResponse

from .providers import ALL_PROVIDERS, PROVIDER_EXAMPLES

router = APIRouter(tags=["connections"])


class AgentConnectLinkRequest(BaseModel):
    customer_id: str
    provider: str


def _verify_agent_secret(authorization: str) -> None:
    expected = f"Bearer {settings.agent_api_secret}"
    if not settings.agent_api_secret or authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid agent secret")


@router.get("/internal/agent/connections")
async def agent_get_connections(
    authorization: str = Header(...),
    x_customer_id: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Return connection config for an agent. Authenticated via shared secret."""
    _verify_agent_secret(authorization)

    result = await db.execute(
        select(CustomerConnection)
        .where(CustomerConnection.customer_id == x_customer_id)
        .where(CustomerConnection.status == "active")
    )
    rows = result.scalars().all()

    connected_providers = {row.provider for row in rows}

    connections = []
    for row in rows:
        conn_info = {
            "provider": row.provider,
            "connection_id": row.nango_connection_id,
            "provider_config_key": row.provider,
        }
        if row.provider in PROVIDER_EXAMPLES:
            conn_info["example"] = PROVIDER_EXAMPLES[row.provider]["example"]
            conn_info["description"] = PROVIDER_EXAMPLES[row.provider]["description"]
        connections.append(conn_info)

    return {
        "proxy_url": settings.nango_server_url,
        "proxy_headers": {
            "Connection-Id": "<connection_id>",
            "Provider-Config-Key": "<provider>",
            "Authorization": f"Bearer {settings.nango_secret_key}",
        },
        "connections": connections,
        "available_providers": [
            {
                "provider": p,
                **(PROVIDER_EXAMPLES.get(p, {})),
            }
            for p in ALL_PROVIDERS
            if p not in connected_providers
        ],
    }


@router.post("/internal/agent/connect-link", response_model=ConnectLinkResponse)
async def agent_create_connect_link(
    body: AgentConnectLinkRequest,
    authorization: str = Header(...),
    r: aioredis.Redis = Depends(get_redis),
):
    """Generate a deep-link URL for an agent to send to a user. Authenticated via shared secret."""
    _verify_agent_secret(authorization)
    token = secrets.token_urlsafe(32)
    await r.set(f"connect-link:{token}", body.customer_id, ex=900)
    base = settings.web_url.rstrip("/")
    url = f"{base}/en/connect/{body.provider}?token={token}"
    return ConnectLinkResponse(url=url)


@router.get("/connect/{provider}/validate")
async def validate_connect_token(
    provider: str,
    token: str,
    r: aioredis.Redis = Depends(get_redis),
):
    customer_id = await r.get(f"connect-link:{token}")
    if not customer_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return {"customer_id": customer_id, "provider": provider}
