import asyncio
import json
import logging
import signal
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
import uvicorn
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .config import settings
from .jobs.destroy import handle_destroy
from .jobs.provision import handle_provision
from .jobs.reactivate import handle_reactivate
from .jobs.resize import handle_resize
from .jobs.suspend import handle_suspend
from .jobs.update import handle_update
from .jobs.update_connections import handle_update_connections
from .k8s import init_k8s

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("operator")

JOB_HANDLERS = {
    "provision": handle_provision,
    "destroy": handle_destroy,
    "suspend": handle_suspend,
    "reactivate": handle_reactivate,
    "update": handle_update,
    "resize": handle_resize,
    "update_connections": handle_update_connections,
}

# Global state
_healthy = False
_redis: redis.Redis | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_shutdown_event = asyncio.Event()


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=2)
        _session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return _session_factory


async def log_job(
    db: AsyncSession,
    *,
    customer_id: str,
    box_id: str | None,
    job_type: str,
    status: str,
    payload: dict,
    error_log: str | None = None,
    started_at: datetime,
) -> None:
    """Write job result to operator_jobs table for auditing."""
    now = datetime.now(timezone.utc)
    await db.execute(
        text("""
            INSERT INTO operator_jobs (customer_id, box_id, job_type, status, payload, error_log, started_at, completed_at)
            VALUES (:customer_id, :box_id, :job_type, :status, :payload, :error_log, :started_at, :completed_at)
        """),
        {
            "customer_id": customer_id,
            "box_id": box_id,
            "job_type": job_type,
            "status": status,
            "payload": json.dumps(payload),
            "error_log": error_log,
            "started_at": started_at,
            "completed_at": now,
        },
    )
    await db.commit()


async def process_job(raw: str) -> None:
    """Parse and dispatch a single job from the queue."""
    job = json.loads(raw)
    job_type = job.get("job_type") or job.get("type")
    customer_id = str(job["customer_id"])
    payload = job.get("payload", {})
    if isinstance(payload, str):
        payload = json.loads(payload) if payload else {}
    box_id = job.get("box_id") or payload.get("box_id")
    # Ensure box_id is available in payload for handlers
    if box_id and "box_id" not in payload:
        payload["box_id"] = box_id

    handler = JOB_HANDLERS.get(job_type)
    if handler is None:
        logger.error("Unknown job type: %s", job_type)
        return

    r = get_redis()
    lock_key = f"operator:lock:{customer_id}"
    lock = r.lock(lock_key, timeout=300, blocking_timeout=30)

    started_at = datetime.now(timezone.utc)
    session_factory = get_session_factory()

    if not lock.acquire(blocking=True):
        logger.error("Could not acquire lock for customer %s", customer_id)
        return

    try:
        async with session_factory() as db:
            # Mark job as running
            await log_job(
                db,
                customer_id=customer_id,
                box_id=box_id,
                job_type=job_type,
                status="running",
                payload=payload,
                started_at=started_at,
            )

            await handler(payload, customer_id, db)

            # Mark job as complete
            await log_job(
                db,
                customer_id=customer_id,
                box_id=box_id,
                job_type=job_type,
                status="complete",
                payload=payload,
                started_at=started_at,
            )
        logger.info("Job %s completed for customer %s", job_type, customer_id)

    except Exception as exc:
        error = traceback.format_exc()
        logger.error("Job %s failed for customer %s: %s", job_type, customer_id, exc)
        try:
            async with session_factory() as db:
                await log_job(
                    db,
                    customer_id=customer_id,
                    box_id=box_id,
                    job_type=job_type,
                    status="failed",
                    payload=payload,
                    error_log=error,
                    started_at=started_at,
                )
        except Exception:
            logger.exception("Failed to log job failure")
    finally:
        try:
            lock.release()
        except redis.exceptions.LockNotOwnedError:
            pass


async def job_loop() -> None:
    """Main loop: BLPOP jobs from Redis and process them."""
    global _healthy

    r = get_redis()
    _healthy = True
    logger.info("Operator started, listening on queue: %s", settings.job_queue)

    while not _shutdown_event.is_set():
        try:
            # BLPOP with 1s timeout so we can check for shutdown
            result = r.blpop(settings.job_queue, timeout=1)
            if result is None:
                continue
            _, raw = result
            await process_job(raw)
        except redis.exceptions.ConnectionError:
            logger.error("Redis connection lost, retrying in 5s...")
            await asyncio.sleep(5)
        except Exception:
            logger.exception("Unexpected error in job loop")
            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Health check HTTP server
# ---------------------------------------------------------------------------

async def health(request: Request) -> JSONResponse:
    if _healthy:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "not ready"}, status_code=503)


@asynccontextmanager
async def lifespan(app: Starlette):
    # Start the job loop as a background task
    init_k8s()
    task = asyncio.create_task(job_loop())
    yield
    _shutdown_event.set()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = Starlette(
    routes=[Route("/healthz", health)],
    lifespan=lifespan,
)


def main() -> None:
    uvicorn.run(
        "openclaw_operator.main:app",
        host="0.0.0.0",
        port=settings.health_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
