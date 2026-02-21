import json

import redis.asyncio as aioredis


async def enqueue_job(
    r: aioredis.Redis,
    *,
    job_id: str,
    job_type: str,
    customer_id: str,
    box_id: str | None = None,
    payload: dict | None = None,
) -> None:
    msg = {"job_id": job_id, "type": job_type, "customer_id": customer_id}
    if box_id is not None:
        msg["box_id"] = box_id
    if payload is not None:
        msg["payload"] = payload
    await r.rpush("operator:jobs", json.dumps(msg, default=str))
