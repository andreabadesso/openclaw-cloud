import json
import logging
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
import stripe
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("billing-worker")

TIER_TOKEN_LIMITS = {
    "starter": 1_000_000,
    "pro": 5_000_000,
    "team": 20_000_000,
}

REDIS_JOB_QUEUE = "operator:jobs"


async def _enqueue_job(
    r: aioredis.Redis,
    *,
    job_type: str,
    customer_id: str,
    box_id: str | None = None,
    payload: dict | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    msg: dict = {"job_id": job_id, "type": job_type, "customer_id": customer_id}
    if box_id is not None:
        msg["box_id"] = box_id
    if payload is not None:
        msg["payload"] = payload
    await r.rpush(REDIS_JOB_QUEUE, json.dumps(msg, default=str))
    logger.info("Enqueued %s job %s for customer %s", job_type, job_id, customer_id)
    return job_id


def _get_tier_from_metadata(metadata: dict) -> str | None:
    return metadata.get("tier")


def _get_tokens_limit(tier: str) -> int:
    return TIER_TOKEN_LIMITS.get(tier, TIER_TOKEN_LIMITS["starter"])


async def handle_checkout_session_completed(
    event: stripe.Event, db: AsyncSession, r: aioredis.Redis
) -> None:
    session = event.data.object
    customer_id = session.metadata.get("openclaw_customer_id")
    if not customer_id:
        logger.error("checkout.session.completed missing openclaw_customer_id in metadata")
        return

    stripe_subscription_id = session.subscription
    stripe_customer_id = session.customer

    # Retrieve subscription to get tier info
    sub = stripe.Subscription.retrieve(stripe_subscription_id)
    price = sub["items"]["data"][0]["price"]
    product = stripe.Product.retrieve(price["product"])
    tier = product.metadata.get("tier", "starter")
    tokens_limit = int(product.metadata.get("tokens_limit", str(_get_tokens_limit(tier))))

    period_start = datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

    # Update customer with stripe_customer_id
    await db.execute(
        text("UPDATE customers SET stripe_customer_id = :stripe_customer_id WHERE id = :id"),
        {"stripe_customer_id": stripe_customer_id, "id": customer_id},
    )

    # Check if subscription already exists (idempotency)
    result = await db.execute(
        text("SELECT id FROM subscriptions WHERE stripe_subscription_id = :sid"),
        {"sid": stripe_subscription_id},
    )
    if result.fetchone():
        logger.info("Subscription %s already exists, skipping", stripe_subscription_id)
        await db.commit()
        return

    # Create subscription
    sub_id = str(uuid.uuid4())
    await db.execute(
        text("""
            INSERT INTO subscriptions (id, customer_id, stripe_subscription_id, stripe_price_id, tier, status, tokens_limit, current_period_start, current_period_end)
            VALUES (:id, :customer_id, :stripe_subscription_id, :stripe_price_id, :tier, 'active', :tokens_limit, :period_start, :period_end)
        """),
        {
            "id": sub_id,
            "customer_id": customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "stripe_price_id": price["id"],
            "tier": tier,
            "tokens_limit": tokens_limit,
            "period_start": period_start,
            "period_end": period_end,
        },
    )

    # Create usage_monthly row
    await db.execute(
        text("""
            INSERT INTO usage_monthly (customer_id, period_start, period_end, tokens_used, tokens_limit)
            VALUES (:customer_id, :period_start, :period_end, 0, :tokens_limit)
            ON CONFLICT (customer_id, period_start) DO NOTHING
        """),
        {
            "customer_id": customer_id,
            "period_start": period_start,
            "period_end": period_end,
            "tokens_limit": tokens_limit,
        },
    )

    await db.commit()

    # Enqueue provision job
    await _enqueue_job(
        r,
        job_type="provision",
        customer_id=customer_id,
        payload={"tier": tier, "subscription_id": sub_id},
    )

    logger.info(
        "Checkout completed: customer=%s tier=%s subscription=%s",
        customer_id, tier, stripe_subscription_id,
    )


async def handle_invoice_payment_succeeded(
    event: stripe.Event, db: AsyncSession, r: aioredis.Redis
) -> None:
    invoice = event.data.object
    stripe_subscription_id = invoice.subscription
    if not stripe_subscription_id:
        logger.info("Invoice %s has no subscription, skipping", invoice.id)
        return

    # Skip the first invoice (handled by checkout.session.completed)
    if invoice.billing_reason == "subscription_create":
        logger.info("Skipping initial subscription invoice %s", invoice.id)
        return

    # Look up subscription
    result = await db.execute(
        text("SELECT id, customer_id, tier, tokens_limit FROM subscriptions WHERE stripe_subscription_id = :sid"),
        {"sid": stripe_subscription_id},
    )
    row = result.fetchone()
    if not row:
        logger.error("No subscription found for stripe_subscription_id=%s", stripe_subscription_id)
        return

    sub_id, customer_id, tier, tokens_limit = row

    # Get period from Stripe subscription
    sub = stripe.Subscription.retrieve(stripe_subscription_id)
    period_start = datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc)
    period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)

    # Update subscription period
    await db.execute(
        text("""
            UPDATE subscriptions SET current_period_start = :period_start, current_period_end = :period_end, updated_at = now()
            WHERE id = :id
        """),
        {"period_start": period_start, "period_end": period_end, "id": sub_id},
    )

    # Reset monthly token counter
    await db.execute(
        text("""
            INSERT INTO usage_monthly (customer_id, period_start, period_end, tokens_used, tokens_limit)
            VALUES (:customer_id, :period_start, :period_end, 0, :tokens_limit)
            ON CONFLICT (customer_id, period_start) DO NOTHING
        """),
        {
            "customer_id": customer_id,
            "period_start": period_start,
            "period_end": period_end,
            "tokens_limit": tokens_limit,
        },
    )

    # Reactivate if suspended
    result = await db.execute(
        text("SELECT status FROM subscriptions WHERE id = :id"),
        {"id": sub_id},
    )
    current_status = result.scalar()
    if current_status == "suspended":
        await db.execute(
            text("UPDATE subscriptions SET status = 'active', updated_at = now() WHERE id = :id"),
            {"id": sub_id},
        )
        await db.commit()

        # Find the box to reactivate
        box_result = await db.execute(
            text("SELECT id FROM boxes WHERE customer_id = :cid AND status = 'suspended' LIMIT 1"),
            {"cid": customer_id},
        )
        box_row = box_result.fetchone()
        box_id = box_row[0] if box_row else None

        await _enqueue_job(
            r,
            job_type="reactivate",
            customer_id=customer_id,
            box_id=box_id,
        )
        logger.info("Reactivated suspended subscription %s", sub_id)
    else:
        await db.commit()

    logger.info("Payment succeeded for subscription %s, token counter reset", sub_id)


async def handle_invoice_payment_failed(
    event: stripe.Event, db: AsyncSession, r: aioredis.Redis
) -> None:
    invoice = event.data.object
    stripe_subscription_id = invoice.subscription
    if not stripe_subscription_id:
        return

    attempt_count = invoice.attempt_count or 0

    # Look up subscription
    result = await db.execute(
        text("SELECT id, customer_id FROM subscriptions WHERE stripe_subscription_id = :sid"),
        {"sid": stripe_subscription_id},
    )
    row = result.fetchone()
    if not row:
        logger.error("No subscription found for stripe_subscription_id=%s", stripe_subscription_id)
        return

    sub_id, customer_id = row

    if attempt_count >= 3:
        # Suspend after 3 failures
        await db.execute(
            text("UPDATE subscriptions SET status = 'suspended', updated_at = now() WHERE id = :id"),
            {"id": sub_id},
        )
        await db.commit()

        # Find box to suspend
        box_result = await db.execute(
            text("SELECT id FROM boxes WHERE customer_id = :cid AND status IN ('active', 'unhealthy') LIMIT 1"),
            {"cid": customer_id},
        )
        box_row = box_result.fetchone()
        box_id = box_row[0] if box_row else None

        await _enqueue_job(
            r,
            job_type="suspend",
            customer_id=customer_id,
            box_id=box_id,
        )
        logger.warning(
            "Payment failed %d times for subscription %s, suspending",
            attempt_count, sub_id,
        )
    else:
        await db.commit()
        logger.warning(
            "Payment failed (attempt %d) for subscription %s",
            attempt_count, sub_id,
        )


async def handle_subscription_updated(
    event: stripe.Event, db: AsyncSession, r: aioredis.Redis
) -> None:
    sub_obj = event.data.object
    stripe_subscription_id = sub_obj.id
    previous_attributes = event.data.get("previous_attributes", {})

    # Look up subscription
    result = await db.execute(
        text("SELECT id, customer_id, tier FROM subscriptions WHERE stripe_subscription_id = :sid"),
        {"sid": stripe_subscription_id},
    )
    row = result.fetchone()
    if not row:
        logger.error("No subscription found for stripe_subscription_id=%s", stripe_subscription_id)
        return

    sub_id, customer_id, old_tier = row

    # Get new tier from Stripe
    price = sub_obj["items"]["data"][0]["price"]
    product = stripe.Product.retrieve(price["product"])
    new_tier = product.metadata.get("tier", old_tier)

    if new_tier == old_tier:
        # No tier change, just update periods if changed
        period_start = datetime.fromtimestamp(sub_obj["current_period_start"], tz=timezone.utc)
        period_end = datetime.fromtimestamp(sub_obj["current_period_end"], tz=timezone.utc)
        await db.execute(
            text("""
                UPDATE subscriptions SET current_period_start = :ps, current_period_end = :pe, updated_at = now()
                WHERE id = :id
            """),
            {"ps": period_start, "pe": period_end, "id": sub_id},
        )
        await db.commit()
        logger.info("Subscription %s updated (no tier change)", sub_id)
        return

    new_tokens_limit = int(product.metadata.get("tokens_limit", str(_get_tokens_limit(new_tier))))

    # Update subscription tier and limits
    await db.execute(
        text("""
            UPDATE subscriptions SET tier = :tier, tokens_limit = :tokens_limit,
                stripe_price_id = :price_id, updated_at = now()
            WHERE id = :id
        """),
        {
            "tier": new_tier,
            "tokens_limit": new_tokens_limit,
            "price_id": price["id"],
            "id": sub_id,
        },
    )

    # Update current usage_monthly token limit
    await db.execute(
        text("""
            UPDATE usage_monthly SET tokens_limit = :tokens_limit
            WHERE customer_id = :customer_id
              AND period_start = (SELECT current_period_start FROM subscriptions WHERE id = :sub_id)
        """),
        {"tokens_limit": new_tokens_limit, "customer_id": customer_id, "sub_id": sub_id},
    )

    await db.commit()

    # Find box and enqueue resize
    box_result = await db.execute(
        text("SELECT id FROM boxes WHERE customer_id = :cid AND status NOT IN ('destroyed', 'destroying') LIMIT 1"),
        {"cid": customer_id},
    )
    box_row = box_result.fetchone()
    box_id = box_row[0] if box_row else None

    await _enqueue_job(
        r,
        job_type="resize",
        customer_id=customer_id,
        box_id=box_id,
        payload={"new_tier": new_tier, "old_tier": old_tier},
    )

    logger.info(
        "Subscription %s tier changed: %s → %s",
        sub_id, old_tier, new_tier,
    )


async def handle_subscription_deleted(
    event: stripe.Event, db: AsyncSession, r: aioredis.Redis
) -> None:
    sub_obj = event.data.object
    stripe_subscription_id = sub_obj.id

    # Look up subscription
    result = await db.execute(
        text("SELECT id, customer_id FROM subscriptions WHERE stripe_subscription_id = :sid"),
        {"sid": stripe_subscription_id},
    )
    row = result.fetchone()
    if not row:
        logger.error("No subscription found for stripe_subscription_id=%s", stripe_subscription_id)
        return

    sub_id, customer_id = row

    # Mark subscription as cancelled
    await db.execute(
        text("UPDATE subscriptions SET status = 'cancelled', updated_at = now() WHERE id = :id"),
        {"id": sub_id},
    )
    await db.commit()

    # Find box and enqueue destroy
    box_result = await db.execute(
        text("SELECT id FROM boxes WHERE customer_id = :cid AND status NOT IN ('destroyed', 'destroying') LIMIT 1"),
        {"cid": customer_id},
    )
    box_row = box_result.fetchone()
    box_id = box_row[0] if box_row else None

    await _enqueue_job(
        r,
        job_type="destroy",
        customer_id=customer_id,
        box_id=box_id,
    )

    logger.info("Subscription %s cancelled, enqueued destroy for customer %s", sub_id, customer_id)


EVENT_HANDLERS = {
    "checkout.session.completed": handle_checkout_session_completed,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "invoice.payment_failed": handle_invoice_payment_failed,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
}
