import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..k8s import (
    patch_deployment_resources,
    patch_resource_quota,
    rollout_restart,
    wait_for_rollout,
)

logger = logging.getLogger(__name__)


async def handle_resize(payload: dict, customer_id: str, db: AsyncSession) -> None:
    """Resize a customer box: update quota and deployment resources for new tier."""

    box_id = payload["box_id"]
    new_tier = payload["new_tier"]

    # 1. Patch ResourceQuota with new tier limits
    patch_resource_quota(customer_id, new_tier)

    # 2. Patch Deployment resource requests/limits
    patch_deployment_resources(customer_id, new_tier)

    # 3. Rollout restart
    rollout_restart(customer_id)

    complete = wait_for_rollout(customer_id, timeout=60)
    if not complete:
        raise TimeoutError(f"Resize rollout not complete within 60s for customer {customer_id}")

    # 4. Update subscription tier in DB
    await db.execute(
        text("""
            UPDATE subscriptions SET tier = :new_tier, updated_at = now()
            WHERE customer_id = :customer_id AND status = 'active'
        """),
        {"new_tier": new_tier, "customer_id": customer_id},
    )
    await db.commit()

    logger.info("Resized customer %s (box %s) to tier %s", customer_id, box_id, new_tier)
