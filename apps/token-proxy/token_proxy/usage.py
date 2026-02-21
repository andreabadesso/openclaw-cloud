from __future__ import annotations

import asyncio
import json
import logging
import time

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from token_proxy.config import USAGE_FLUSH_BATCH_SIZE, USAGE_FLUSH_INTERVAL_S

logger = logging.getLogger(__name__)

STREAM_KEY = "usage:events"
CONSUMER_GROUP = "proxy-consumers"
CONSUMER_NAME = "proxy-worker"


async def push_usage_event(
    redis: Redis,
    customer_id: str,
    box_id: str | None,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    request_id: str,
) -> None:
    """Push a usage event to the Redis stream (fire-and-forget)."""
    await redis.xadd(
        STREAM_KEY,
        {
            "customer_id": customer_id,
            "box_id": box_id or "",
            "model": model,
            "prompt_tokens": str(prompt_tokens),
            "completion_tokens": str(completion_tokens),
            "request_id": request_id,
            "timestamp": str(time.time()),
        },
    )


async def start_usage_consumer(
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Background task: consume usage events from Redis stream, batch write to Postgres."""
    # Create consumer group if it doesn't exist
    try:
        await redis.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception:
        pass  # Group already exists

    batch: list[dict] = []
    last_flush = time.monotonic()

    while True:
        try:
            # Read pending + new messages
            messages = await redis.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_KEY: ">"},
                count=USAGE_FLUSH_BATCH_SIZE,
                block=int(USAGE_FLUSH_INTERVAL_S * 1000),
            )

            if messages:
                for _stream, entries in messages:
                    for msg_id, fields in entries:
                        batch.append(
                            {
                                "msg_id": msg_id,
                                "customer_id": fields.get("customer_id", ""),
                                "box_id": fields.get("box_id", ""),
                                "model": fields.get("model", ""),
                                "prompt_tokens": int(fields.get("prompt_tokens", 0)),
                                "completion_tokens": int(fields.get("completion_tokens", 0)),
                                "request_id": fields.get("request_id", ""),
                            }
                        )

            elapsed = time.monotonic() - last_flush
            if batch and (len(batch) >= USAGE_FLUSH_BATCH_SIZE or elapsed >= USAGE_FLUSH_INTERVAL_S):
                await _flush_batch(batch, redis, session_factory)
                # ACK processed messages
                msg_ids = [e["msg_id"] for e in batch]
                if msg_ids:
                    await redis.xack(STREAM_KEY, CONSUMER_GROUP, *msg_ids)
                batch = []
                last_flush = time.monotonic()

        except asyncio.CancelledError:
            # Flush remaining on shutdown
            if batch:
                try:
                    await _flush_batch(batch, redis, session_factory)
                    msg_ids = [e["msg_id"] for e in batch]
                    if msg_ids:
                        await redis.xack(STREAM_KEY, CONSUMER_GROUP, *msg_ids)
                except Exception:
                    logger.exception("Failed to flush remaining batch on shutdown")
            raise
        except Exception:
            logger.exception("Error in usage consumer loop")
            await asyncio.sleep(1)


async def _flush_batch(
    batch: list[dict],
    redis: Redis,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Write a batch of usage events to Postgres and update caches."""
    if not batch:
        return

    async with session_factory() as session:
        async with session.begin():
            # Insert individual events
            for event in batch:
                if not event["box_id"]:
                    continue
                await session.execute(
                    text(
                        "INSERT INTO usage_events "
                        "(customer_id, box_id, model, prompt_tokens, completion_tokens, request_id) "
                        "VALUES (:customer_id, :box_id, :model, :prompt_tokens, :completion_tokens, :request_id) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {
                        "customer_id": event["customer_id"],
                        "box_id": event["box_id"],
                        "model": event["model"],
                        "prompt_tokens": event["prompt_tokens"],
                        "completion_tokens": event["completion_tokens"],
                        "request_id": event["request_id"],
                    },
                )

            # Aggregate by customer and update monthly totals
            customer_totals: dict[str, int] = {}
            for event in batch:
                cid = event["customer_id"]
                total = event["prompt_tokens"] + event["completion_tokens"]
                customer_totals[cid] = customer_totals.get(cid, 0) + total

            for customer_id, total_tokens in customer_totals.items():
                await session.execute(
                    text(
                        "UPDATE usage_monthly "
                        "SET tokens_used = tokens_used + :total "
                        "WHERE customer_id = :cid "
                        "  AND period_start <= now() "
                        "  AND period_end > now()"
                    ),
                    {"total": total_tokens, "cid": customer_id},
                )

    # Update Redis caches for affected customers
    for customer_id in customer_totals:
        cache_key = f"limit:{customer_id}"
        cached = await redis.get(cache_key)
        if cached is not None:
            data = json.loads(cached)
            data["used"] = data["used"] + customer_totals[customer_id]
            await redis.set(cache_key, json.dumps(data), keepttl=True)

    logger.info("Flushed %d usage events for %d customers", len(batch), len(customer_totals))
