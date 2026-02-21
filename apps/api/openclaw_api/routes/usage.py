from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from openclaw_api.deps import get_current_customer_id, get_db
from openclaw_api.models import UsageMonthly
from openclaw_api.schemas import UsageResponse

router = APIRouter(prefix="/me", tags=["usage"])


@router.get("/usage", response_model=UsageResponse)
async def get_my_usage(
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    now = func.now()
    result = await db.execute(
        select(UsageMonthly)
        .where(UsageMonthly.customer_id == customer_id)
        .where(UsageMonthly.period_start <= now)
        .where(UsageMonthly.period_end > now)
        .order_by(UsageMonthly.period_start.desc())
        .limit(1)
    )
    usage = result.scalar_one_or_none()
    if not usage:
        raise HTTPException(status_code=404, detail="No usage data for current period")

    pct = round(usage.tokens_used / usage.tokens_limit * 100, 1) if usage.tokens_limit > 0 else 0.0

    return UsageResponse(
        tokens_used=usage.tokens_used,
        tokens_limit=usage.tokens_limit,
        pct_used=pct,
        period_start=usage.period_start,
        period_end=usage.period_end,
    )
