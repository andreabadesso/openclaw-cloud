import json
import secrets

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.config import settings
from openclaw_api.deps import get_current_customer_id, get_db, get_redis
from openclaw_api.models import (
    Box,
    BoxStatus,
    CustomerConnection,
    JobStatus,
    JobType,
    OperatorJob,
)
from openclaw_api.nango_client import NangoClient, get_nango_client
from openclaw_api.schemas import (
    ConnectLinkRequest,
    ConnectLinkResponse,
    ConnectSessionResponse,
    ConnectionListResponse,
    ConnectionResponse,
)

router = APIRouter(tags=["connections"])


# --- Customer-facing routes ---


@router.post("/me/connections/{provider}/authorize", response_model=ConnectSessionResponse)
async def authorize_connection(
    provider: str,
    customer_id: str = Depends(get_current_customer_id),
    nango: NangoClient = Depends(get_nango_client),
):
    try:
        result = await nango.create_connect_session(customer_id, provider)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nango error: {exc}") from exc

    return ConnectSessionResponse(
        session_token=result["data"]["token"],
        connect_url=f"{settings.nango_public_url}/connect/{result['data']['token']}",
    )


@router.get("/me/connections", response_model=ConnectionListResponse)
async def list_connections(
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomerConnection)
        .where(CustomerConnection.customer_id == customer_id)
        .where(CustomerConnection.status == "active")
    )
    rows = result.scalars().all()

    return ConnectionListResponse(
        connections=[
            ConnectionResponse(
                id=row.nango_connection_id,
                provider=row.provider,
                status="connected",
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.post("/me/connections/{provider}/confirm")
async def confirm_connection(
    provider: str,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
    nango: NangoClient = Depends(get_nango_client),
):
    """Called by the frontend after a successful OAuth popup to sync the connection locally."""
    # Verify the connection exists in Nango
    connection_id = f"{customer_id}_{provider}"
    try:
        connections = await nango.list_connections(search=customer_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nango error: {exc}") from exc

    nango_conn = next(
        (c for c in connections if c.get("provider_config_key", c.get("provider", "")) == provider),
        None,
    )
    if not nango_conn:
        raise HTTPException(status_code=404, detail="Connection not found in Nango")

    actual_connection_id = nango_conn.get("connection_id", connection_id)

    # Upsert local tracking record
    result = await db.execute(
        select(CustomerConnection)
        .where(CustomerConnection.customer_id == customer_id)
        .where(CustomerConnection.provider == provider)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.status = "active"
        existing.nango_connection_id = actual_connection_id
    else:
        db.add(CustomerConnection(
            customer_id=customer_id,
            provider=provider,
            nango_connection_id=actual_connection_id,
        ))

    # Enqueue update_connections job so the pod secret gets updated
    box_result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status == BoxStatus.active)
        .limit(1)
    )
    box = box_result.scalar_one_or_none()
    if box:
        job = OperatorJob(
            customer_id=customer_id,
            box_id=box.id,
            job_type=JobType.update_connections,
            status=JobStatus.queued,
            payload={"provider": provider, "connection_id": actual_connection_id},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        await r.rpush(
            "operator:jobs",
            json.dumps({
                "job_id": job.id,
                "type": "update_connections",
                "customer_id": customer_id,
                "box_id": box.id,
            }),
        )
    else:
        await db.commit()

    return {"status": "ok", "provider": provider, "connection_id": actual_connection_id}


@router.delete("/me/connections/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: str,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
    nango: NangoClient = Depends(get_nango_client),
):
    # Delete from Nango
    try:
        await nango.delete_connection(connection_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nango error: {exc}") from exc

    # Soft-delete local record if it exists
    result = await db.execute(
        select(CustomerConnection)
        .where(CustomerConnection.customer_id == customer_id)
        .where(CustomerConnection.nango_connection_id == connection_id)
        .where(CustomerConnection.status == "active")
    )
    conn = result.scalar_one_or_none()
    if conn:
        conn.status = "deleted"

    # Enqueue update_connections job for any active box
    box_result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status == BoxStatus.active)
        .limit(1)
    )
    box = box_result.scalar_one_or_none()
    if box:
        job = OperatorJob(
            customer_id=customer_id,
            box_id=box.id,
            job_type=JobType.update_connections,
            status=JobStatus.queued,
            payload={"deleted_connection_id": connection_id},
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        await r.rpush(
            "operator:jobs",
            json.dumps({
                "job_id": job.id,
                "type": "update_connections",
                "customer_id": customer_id,
                "box_id": box.id,
            }),
        )
    else:
        await db.commit()


@router.post("/me/connections/{connection_id}/reconnect", response_model=ConnectSessionResponse)
async def reconnect_connection(
    connection_id: str,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    nango: NangoClient = Depends(get_nango_client),
):
    # Look up the provider from the local record
    result = await db.execute(
        select(CustomerConnection)
        .where(CustomerConnection.customer_id == customer_id)
        .where(CustomerConnection.nango_connection_id == connection_id)
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    try:
        session_result = await nango.create_connect_session(customer_id, conn.provider)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nango error: {exc}") from exc

    return ConnectSessionResponse(
        session_token=session_result["data"]["token"],
        connect_url=f"{settings.nango_public_url}/connect/{session_result['data']['token']}",
    )


# --- Internal routes (for deep links) ---


@router.post("/internal/connect-link", response_model=ConnectLinkResponse)
async def create_connect_link(
    body: ConnectLinkRequest,
    customer_id: str = Depends(get_current_customer_id),
    r: aioredis.Redis = Depends(get_redis),
):
    token = secrets.token_urlsafe(32)
    await r.set(f"connect-link:{token}", customer_id, ex=900)  # 15 min TTL
    base = settings.cors_origins.split(",")[0]
    url = f"{base}/connect/{body.provider}?token={token}"
    return ConnectLinkResponse(url=url)


class AgentConnectLinkRequest(BaseModel):
    customer_id: str
    provider: str


ALL_PROVIDERS = ["github", "google", "slack", "linear", "notion", "jira"]

PROVIDER_EXAMPLES: dict[str, dict] = {
    "github": {
        "name": "GitHub",
        "example": "GET /proxy/user/repos",
        "description": "GitHub API (repos, issues, PRs, code search)",
    },
    "slack": {
        "name": "Slack",
        "example": "POST /proxy/chat.postMessage with body {\"channel\":\"#general\",\"text\":\"Hello!\"}",
        "description": "Slack API (messages, channels, users)",
    },
    "linear": {
        "name": "Linear",
        "example": "POST /proxy/graphql with body {\"query\":\"{ issues { nodes { title state { name } } } }\"}",
        "description": "Linear API (issues, projects, cycles)",
    },
    "notion": {
        "name": "Notion",
        "example": "POST /proxy/v1/search with headers Notion-Version: 2022-06-28 and body {\"query\":\"\"}",
        "description": "Notion API (pages, databases, blocks)",
    },
    "google": {
        "name": "Google",
        "example": "GET /proxy/calendar/v3/calendars/primary/events?maxResults=10",
        "description": "Google API (calendar, drive, gmail)",
    },
    "jira": {
        "name": "Jira",
        "example": "GET /proxy/rest/api/3/search?jql=assignee=currentUser()",
        "description": "Jira API (issues, projects, boards)",
    },
}


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
    base = settings.cors_origins.split(",")[0]
    url = f"{base}/connect/{body.provider}?token={token}"
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
