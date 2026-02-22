from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.deps import get_db, get_redis
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
from openclaw_api.schemas import (
    BoxListItem,
    BoxListResponse,
    CustomerListResponse,
    CustomerResponse,
    JobEnqueuedResponse,
    ProvisionRequest,
    ProvisionResponse,
    ResizeRequest,
    UpdateBoxRequest,
)

TIER_TOKEN_LIMITS = {
    "starter": 1_000_000,
    "pro": 5_000_000,
    "team": 20_000_000,
}

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post("/provision", response_model=ProvisionResponse)
async def provision_box(
    body: ProvisionRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    # Create or fetch customer
    result = await db.execute(select(Customer).where(Customer.email == body.customer_email))
    customer = result.scalar_one_or_none()

    if customer is None:
        customer = Customer(email=body.customer_email)
        db.add(customer)
        await db.flush()

    # Validate niche if provided
    if body.niche and body.niche not in NICHES:
        raise HTTPException(status_code=400, detail=f"Unknown niche: {body.niche}")

    # Check for existing active box
    existing = await db.execute(
        select(Box)
        .where(Box.customer_id == customer.id)
        .where(Box.status.notin_([BoxStatus.destroyed, BoxStatus.destroying]))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Customer already has an active box")

    # Create subscription
    now = datetime.now(timezone.utc)
    tokens_limit = TIER_TOKEN_LIMITS[body.tier]
    subscription = Subscription(
        customer_id=customer.id,
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
        customer_id=customer.id,
        subscription_id=subscription.id,
        k8s_namespace=f"customer-{customer.id}",
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
        customer_id=customer.id,
        period_start=now,
        period_end=now + timedelta(days=30),
        tokens_limit=tokens_limit,
    )
    db.add(usage)

    # Create operator job record
    job = OperatorJob(
        customer_id=customer.id,
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
    await db.refresh(customer)
    await db.refresh(box)
    await db.refresh(job)

    # Enqueue to Redis for operator
    await enqueue_job(
        r, job_id=job.id, job_type="provision",
        customer_id=customer.id, box_id=box.id, payload=job.payload,
    )

    return ProvisionResponse(customer_id=customer.id, box_id=box.id, job_id=job.id)


@router.post("/destroy/{box_id}", response_model=JobEnqueuedResponse)
async def destroy_box(
    box_id: str,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Box).where(Box.id == box_id))
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if box.status in (BoxStatus.destroyed, BoxStatus.destroying):
        raise HTTPException(status_code=409, detail="Box is already destroyed or destroying")

    job = OperatorJob(
        customer_id=box.customer_id,
        box_id=box.id,
        job_type=JobType.destroy,
        status=JobStatus.queued,
    )
    db.add(job)
    box.status = BoxStatus.destroying
    await db.commit()
    await db.refresh(job)

    await enqueue_job(
        r, job_id=job.id, job_type="destroy",
        customer_id=box.customer_id, box_id=box.id,
    )

    return JobEnqueuedResponse(job_id=job.id, box_id=box.id)


@router.post("/suspend/{box_id}", response_model=JobEnqueuedResponse)
async def suspend_box(
    box_id: str,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Box).where(Box.id == box_id))
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if box.status != BoxStatus.active:
        raise HTTPException(status_code=409, detail=f"Box must be active to suspend, current status: {box.status}")

    job = OperatorJob(
        customer_id=box.customer_id,
        box_id=box.id,
        job_type=JobType.suspend,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_job(
        r, job_id=job.id, job_type="suspend",
        customer_id=box.customer_id, box_id=box.id,
    )

    return JobEnqueuedResponse(job_id=job.id, box_id=box.id)


@router.post("/reactivate/{box_id}", response_model=JobEnqueuedResponse)
async def reactivate_box(
    box_id: str,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Box).where(Box.id == box_id))
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if box.status != BoxStatus.suspended:
        raise HTTPException(status_code=409, detail=f"Box must be suspended to reactivate, current status: {box.status}")

    job = OperatorJob(
        customer_id=box.customer_id,
        box_id=box.id,
        job_type=JobType.reactivate,
        status=JobStatus.queued,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_job(
        r, job_id=job.id, job_type="reactivate",
        customer_id=box.customer_id, box_id=box.id,
    )

    return JobEnqueuedResponse(job_id=job.id, box_id=box.id)


@router.patch("/update/{box_id}", response_model=JobEnqueuedResponse)
async def update_box(
    box_id: str,
    body: UpdateBoxRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Box).where(Box.id == box_id))
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if box.status not in (BoxStatus.active, BoxStatus.updating):
        raise HTTPException(status_code=409, detail=f"Box must be active to update, current status: {box.status}")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    secret_data = {}
    if body.telegram_user_ids is not None:
        secret_data["TELEGRAM_ALLOW_FROM"] = ",".join(str(uid) for uid in body.telegram_user_ids)
    if body.model is not None:
        secret_data["OPENCLAW_MODEL"] = body.model
    if body.thinking_level is not None:
        secret_data["OPENCLAW_THINKING"] = body.thinking_level

    for key, value in updates.items():
        setattr(box, key, value)

    job = OperatorJob(
        customer_id=box.customer_id,
        box_id=box.id,
        job_type=JobType.update,
        status=JobStatus.queued,
        payload={"box_id": box.id, "secret_data": secret_data},
    )
    db.add(job)
    box.status = BoxStatus.updating
    await db.commit()
    await db.refresh(job)

    await enqueue_job(
        r, job_id=job.id, job_type="update",
        customer_id=box.customer_id, box_id=box.id,
        payload={"box_id": box.id, "secret_data": secret_data},
    )

    return JobEnqueuedResponse(job_id=job.id, box_id=box.id)


@router.post("/resize/{box_id}", response_model=JobEnqueuedResponse)
async def resize_box(
    box_id: str,
    body: ResizeRequest,
    db: AsyncSession = Depends(get_db),
    r: aioredis.Redis = Depends(get_redis),
):
    result = await db.execute(select(Box).where(Box.id == box_id))
    box = result.scalar_one_or_none()
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    if box.status not in (BoxStatus.active, BoxStatus.updating):
        raise HTTPException(status_code=409, detail=f"Box must be active to resize, current status: {box.status}")

    # Look up current subscription tier
    sub_result = await db.execute(
        select(Subscription).where(Subscription.id == box.subscription_id)
    )
    subscription = sub_result.scalar_one_or_none()
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if subscription.tier.value == body.new_tier:
        raise HTTPException(status_code=409, detail="Box is already on this tier")

    subscription.tier = Tier(body.new_tier)
    subscription.tokens_limit = TIER_TOKEN_LIMITS[body.new_tier]

    job = OperatorJob(
        customer_id=box.customer_id,
        box_id=box.id,
        job_type=JobType.resize,
        status=JobStatus.queued,
        payload={"box_id": box.id, "new_tier": body.new_tier},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await enqueue_job(
        r, job_id=job.id, job_type="resize",
        customer_id=box.customer_id, box_id=box.id,
        payload={"box_id": box.id, "new_tier": body.new_tier},
    )

    return JobEnqueuedResponse(job_id=job.id, box_id=box.id)


@router.get("/boxes", response_model=BoxListResponse)
async def list_all_boxes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Box).where(Box.status != BoxStatus.destroyed).order_by(Box.created_at.desc())
    )
    boxes = result.scalars().all()
    return BoxListResponse(boxes=[BoxListItem.model_validate(b) for b in boxes])


@router.get("/customers", response_model=CustomerListResponse)
async def list_all_customers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Customer).where(Customer.deleted_at.is_(None)).order_by(Customer.created_at.desc())
    )
    customers = result.scalars().all()
    return CustomerListResponse(customers=[CustomerResponse.model_validate(c) for c in customers])
