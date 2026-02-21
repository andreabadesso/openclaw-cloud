import secrets

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.config import settings
from openclaw_api.deps import get_active_box_or_none, get_current_customer_id, get_db, get_redis
from openclaw_api.jobs import enqueue_job
from openclaw_api.models import (
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
    try:
        all_connections = await nango.list_connections()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Nango error: {exc}") from exc

    nango_conn = next(
        (
            c for c in all_connections
            if c.get("provider_config_key", c.get("provider", "")) == provider
            and c.get("end_user", {}).get("id") == customer_id
        ),
        None,
    )
    if not nango_conn:
        raise HTTPException(status_code=404, detail="Connection not found in Nango")

    actual_connection_id = nango_conn.get("connection_id", f"{customer_id}_{provider}")

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
    box = await get_active_box_or_none(customer_id, db)
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
        await enqueue_job(
            r, job_id=job.id, job_type="update_connections",
            customer_id=customer_id, box_id=box.id,
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
    box = await get_active_box_or_none(customer_id, db)
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
        await enqueue_job(
            r, job_id=job.id, job_type="update_connections",
            customer_id=customer_id, box_id=box.id,
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
