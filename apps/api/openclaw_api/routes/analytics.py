from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from openclaw_api.deps import get_current_customer_id, get_db
from openclaw_api.schemas import (
    AnalyticsResponse,
    BrowserSessionsSummary,
    PodMetricsPoint,
    TokenUsageSummary,
)

router = APIRouter(prefix="/me", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    hours: int = Query(default=24, ge=1, le=168),
    customer_id: str = Depends(get_current_customer_id),
    db: AsyncSession = Depends(get_db),
):
    # Token usage — current period
    row = (await db.execute(text("""
        SELECT tokens_used, tokens_limit, period_start, period_end
        FROM usage_monthly
        WHERE customer_id = :cid AND period_start <= now() AND period_end > now()
        ORDER BY period_start DESC LIMIT 1
    """), {"cid": customer_id})).first()

    token_usage = TokenUsageSummary(
        tokens_used=row.tokens_used if row else 0,
        tokens_limit=row.tokens_limit if row else 0,
        period_start=row.period_start if row else None,
        period_end=row.period_end if row else None,
    )

    # Browser sessions — last N hours
    brow = (await db.execute(text("""
        SELECT count(*)::int AS cnt, coalesce(sum(duration_ms), 0)::bigint AS total_ms
        FROM browser_sessions
        WHERE customer_id = :cid AND started_at > now() - make_interval(hours => :hours)
    """), {"cid": customer_id, "hours": hours})).first()

    browser_sessions = BrowserSessionsSummary(
        session_count=brow.cnt if brow else 0,
        total_duration_ms=brow.total_ms if brow else 0,
    )

    # Tier — from active subscription
    tier_row = (await db.execute(text("""
        SELECT s.tier FROM subscriptions s
        JOIN boxes b ON b.subscription_id = s.id
        WHERE b.customer_id = :cid AND b.status != 'destroyed'
        ORDER BY b.created_at DESC LIMIT 1
    """), {"cid": customer_id})).first()
    tier = tier_row.tier if tier_row else "starter"

    # Pod metrics — combine recent snapshots + hourly history
    # Recent snapshots (last 2h, raw)
    snap_rows = (await db.execute(text("""
        SELECT cpu_millicores, memory_bytes, collected_at AS ts
        FROM pod_metrics_snapshots
        WHERE customer_id = :cid AND collected_at > now() - make_interval(hours => :hours)
        ORDER BY collected_at
    """), {"cid": customer_id, "hours": hours})).all()

    # Hourly buckets (older data)
    hourly_rows = (await db.execute(text("""
        SELECT avg_cpu AS cpu_millicores, avg_memory AS memory_bytes, hour AS ts
        FROM pod_metrics_hourly
        WHERE customer_id = :cid AND hour > now() - make_interval(hours => :hours)
        ORDER BY hour
    """), {"cid": customer_id, "hours": hours})).all()

    series = [
        PodMetricsPoint(cpu_millicores=r.cpu_millicores, memory_bytes=r.memory_bytes, ts=r.ts)
        for r in hourly_rows
    ] + [
        PodMetricsPoint(cpu_millicores=r.cpu_millicores, memory_bytes=r.memory_bytes, ts=r.ts)
        for r in snap_rows
    ]
    # Sort combined series by timestamp
    series.sort(key=lambda p: p.ts)

    latest = series[-1] if series else None

    return AnalyticsResponse(
        token_usage=token_usage,
        browser_sessions=browser_sessions,
        pod_metrics_latest=latest,
        pod_metrics_series=series,
        tier=tier,
    )
