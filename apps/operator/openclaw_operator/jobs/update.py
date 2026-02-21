import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..k8s import patch_config_secret, rollout_restart, wait_for_rollout

logger = logging.getLogger(__name__)


async def handle_update(payload: dict, customer_id: str, db: AsyncSession) -> None:
    """Update a customer box config: patch secret, rollout restart."""

    box_id = payload["box_id"]
    secret_data = payload["secret_data"]  # dict of env vars to update

    # 1. Patch K8s Secret with new config
    patch_config_secret(customer_id, secret_data)

    # 2. Rollout restart Deployment
    rollout_restart(customer_id)

    # 3. Wait for rollout complete
    complete = wait_for_rollout(customer_id, timeout=60)
    if not complete:
        raise TimeoutError(f"Rollout not complete within 60s for customer {customer_id}")

    # 4. Update last_updated
    await db.execute(
        text("UPDATE boxes SET last_updated = now() WHERE id = :box_id"),
        {"box_id": box_id},
    )
    await db.commit()

    logger.info("Updated customer %s (box %s)", customer_id, box_id)
