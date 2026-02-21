import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..k8s import scale_deployment

logger = logging.getLogger(__name__)


async def handle_suspend(payload: dict, customer_id: str, db: AsyncSession) -> None:
    """Suspend a customer box: scale deployment to 0."""

    box_id = payload["box_id"]

    # 1. Scale Deployment to 0 replicas
    scale_deployment(customer_id, replicas=0)

    # 2. Update box status
    await db.execute(
        text("UPDATE boxes SET status = 'suspended' WHERE id = :box_id"),
        {"box_id": box_id},
    )
    await db.commit()

    logger.info("Suspended customer %s (box %s)", customer_id, box_id)
