import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..k8s import scale_deployment

logger = logging.getLogger(__name__)


async def handle_reactivate(payload: dict, customer_id: str, db: AsyncSession) -> None:
    """Reactivate a suspended customer box: scale deployment back to 1."""

    box_id = payload["box_id"]

    # 1. Scale Deployment back to 1 replica
    scale_deployment(customer_id, replicas=1)

    # 2. Update box status
    await db.execute(
        text("UPDATE boxes SET status = 'active' WHERE id = :box_id"),
        {"box_id": box_id},
    )
    await db.commit()

    logger.info("Reactivated customer %s (box %s)", customer_id, box_id)
