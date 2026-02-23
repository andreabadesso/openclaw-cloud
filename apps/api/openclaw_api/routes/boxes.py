from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.deps import get_active_box_or_none, get_current_customer_id, get_db, get_redis
from openclaw_api.jobs import enqueue_job
from openclaw_api.models import (
    Box,
    BoxStatus,
    Customer,
    JobStatus,
    JobType,
    OperatorJob,
    Subscription,
    SubscriptionStatus,
    Tier,
    UsageMonthly,
)
from openclaw_api.niches import NICHES
from openclaw_api.schemas import BoxResponse, JobEnqueuedResponse, ProvisionResponse, SetupRequest, UpdateBoxRequest

router = APIRouter(prefix="/me", tags=["boxes"])


@router.get("/box", response_model=BoxResponse)
async def get_my_box(
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status != BoxStatus.destroyed)
        .order_by(Box.created_at.desc())
        .limit(1)
    )
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="No active box found")
    return box


@router.post("/box/update", response_model=JobEnqueuedResponse)
async def update_my_box(
    body: UpdateBoxRequest,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    box = await get_active_box_or_none(customer_id, db)
    if not box:
        raise HTTPException(status_code=404, detail="No active box found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    for key, value in updates.items():
        setattr(box, key, value)

    job = OperatorJob(
        customer_id=customer_id,
        box_id=box.id,
        job_type=JobType.update,
        status=JobStatus.queued,
        payload=updates,
    )
    db.add(job)
    box.status = BoxStatus.updating
    await db.commit()
    await db.refresh(job)

    await enqueue_job(
        r, job_id=job.id, job_type="update",
        customer_id=customer_id, box_id=box.id, payload=updates,
    )

    return JobEnqueuedResponse(job_id=job.id, box_id=box.id)


TIER_TOKEN_LIMITS = {
    "starter": 1_000_000,
    "pro": 5_000_000,
    "team": 20_000_000,
}


@router.post("/setup", response_model=ProvisionResponse)
async def setup_box(
    body: SetupRequest,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    # Validate niche if provided
    if body.niche and body.niche not in NICHES:
        raise HTTPException(status_code=400, detail=f"Unknown niche: {body.niche}")

    # Check for existing active box
    existing = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status.notin_([BoxStatus.destroyed, BoxStatus.destroying]))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Customer already has an active box")

    # Create subscription
    now = datetime.now(timezone.utc)
    tokens_limit = TIER_TOKEN_LIMITS[body.tier]
    subscription = Subscription(
        customer_id=customer_id,
        tier=Tier(body.tier),
        status=SubscriptionStatus.active,
        tokens_limit=tokens_limit,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    db.add(subscription)
    await db.flush()

    # Create box
    box = Box(
        customer_id=customer_id,
        subscription_id=subscription.id,
        k8s_namespace=f"customer-{customer_id}",
        telegram_user_ids=[body.telegram_user_id],
        language=body.language,
        model=body.model,
        thinking_level=body.thinking_level,
        niche=body.niche,
        status=BoxStatus.pending,
    )
    db.add(box)
    await db.flush()

    # Create usage record
    usage = UsageMonthly(
        customer_id=customer_id,
        period_start=now,
        period_end=now + timedelta(days=30),
        tokens_limit=tokens_limit,
    )
    db.add(usage)

    # Create operator job record
    job = OperatorJob(
        customer_id=customer_id,
        box_id=box.id,
        job_type=JobType.provision,
        status=JobStatus.queued,
        payload={
            "telegram_bot_token": body.telegram_bot_token,
            "telegram_user_id": body.telegram_user_id,
            "tier": body.tier,
            "model": body.model,
            "thinking_level": body.thinking_level,
            "language": body.language,
            "niche": body.niche,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(box)
    await db.refresh(job)

    # Enqueue to Redis for operator
    await enqueue_job(
        r, job_id=job.id, job_type="provision",
        customer_id=customer_id, box_id=box.id, payload=job.payload,
    )

    return ProvisionResponse(customer_id=customer_id, box_id=box.id, job_id=job.id)
