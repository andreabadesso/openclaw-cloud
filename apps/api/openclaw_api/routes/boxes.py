from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.deps import get_current_customer_id, get_db, get_redis
from openclaw_api.jobs import enqueue_job
from openclaw_api.models import (
    Box,
    BoxStatus,
    Bundle,
    Customer,
    JobStatus,
    JobType,
    OperatorJob,
    Subscription,
    SubscriptionStatus,
    Tier,
    UsageMonthly,
)
from openclaw_api.schemas import (
    BoxListResponse,
    BoxResponse,
    JobEnqueuedResponse,
    ProvisionResponse,
    SetupRequest,
    UpdateBoxRequest,
)

router = APIRouter(prefix="/me", tags=["boxes"])


@router.get("/boxes", response_model=BoxListResponse)
async def get_my_boxes(
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status != BoxStatus.destroyed)
        .order_by(Box.created_at.desc())
    )
    boxes = result.scalars().all()
    return BoxListResponse(boxes=boxes)


@router.get("/box", response_model=BoxResponse)
async def get_my_box(
    box_id: str | None = Query(None),
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    query = select(Box).where(Box.customer_id == customer_id).where(Box.status != BoxStatus.destroyed)
    if box_id:
        query = query.where(Box.id == box_id)
    else:
        query = query.order_by(Box.created_at.desc()).limit(1)
    result = await db.execute(query)
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="No active box found")
    return box


@router.post("/box/{box_id}/update", response_model=JobEnqueuedResponse)
async def update_box_by_id(
    box_id: str,
    body: UpdateBoxRequest,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(
        select(Box)
        .where(Box.id == box_id, Box.customer_id == customer_id)
        .where(Box.status != BoxStatus.destroyed)
    )
    box = result.scalar_one_or_none()
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


@router.post("/box/update", response_model=JobEnqueuedResponse)
async def update_my_box_legacy(
    body: UpdateBoxRequest,
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    """Legacy endpoint: updates the most recently created active box."""
    result = await db.execute(
        select(Box)
        .where(Box.customer_id == customer_id)
        .where(Box.status == BoxStatus.active)
        .order_by(Box.created_at.desc())
        .limit(1)
    )
    box = result.scalar_one_or_none()
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
    # Validate bundle
    result = await db.execute(
        select(Bundle).where(Bundle.id == body.bundle_id, Bundle.status == "published")
    )
    bundle = result.scalar_one_or_none()
    if not bundle:
        raise HTTPException(status_code=400, detail="Invalid or unpublished bundle")

    # Apply bundle defaults for optional fields
    model = body.model or bundle.default_model
    thinking_level = body.thinking_level or bundle.default_thinking_level
    language = body.language or bundle.default_language

    # Count existing boxes for unique namespace suffix
    count_result = await db.execute(
        select(func.count()).select_from(Box).where(Box.customer_id == customer_id)
    )
    box_count = count_result.scalar() or 0
    namespace_suffix = f"-{box_count + 1}" if box_count > 0 else ""

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
        k8s_namespace=f"customer-{customer_id}{namespace_suffix}",
        telegram_user_ids=[body.telegram_user_id],
        language=language,
        model=model,
        thinking_level=thinking_level,
        bundle_id=bundle.id,
        niche=bundle.slug,
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
            "model": model,
            "thinking_level": thinking_level,
            "language": language,
            "bundle_prompts": bundle.prompts,
            "bundle_mcp_servers": bundle.mcp_servers,
            "bundle_skills": bundle.skills,
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
