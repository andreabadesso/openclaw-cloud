import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.deps import get_active_box_or_none, get_current_customer_id, get_db, get_redis
from openclaw_api.jobs import enqueue_job
from openclaw_api.models import Box, BoxStatus, OperatorJob, JobType, JobStatus
from openclaw_api.schemas import BoxResponse, UpdateBoxRequest, JobEnqueuedResponse

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
