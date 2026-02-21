import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..k8s import delete_namespace

logger = logging.getLogger(__name__)


async def handle_destroy(payload: dict, customer_id: str, db: AsyncSession) -> None:
    """Destroy a customer box: delete namespace, revoke proxy token, update DB."""

    box_id = payload["box_id"]
    proxy_token_id = payload.get("proxy_token_id")

    # 1. Delete K8s namespace (cascades all resources)
    delete_namespace(customer_id)

    # 2. Revoke proxy token with token-proxy
    if proxy_token_id:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{settings.token_proxy_url}/internal/tokens/{proxy_token_id}",
                timeout=10,
            )
            resp.raise_for_status()
        logger.info("Revoked proxy token %s", proxy_token_id)

    # 3. Update box status
    await db.execute(
        text("UPDATE boxes SET status = 'destroyed', destroyed_at = now() WHERE id = :box_id"),
        {"box_id": box_id},
    )
    await db.commit()

    logger.info("Destroyed customer %s (box %s)", customer_id, box_id)
