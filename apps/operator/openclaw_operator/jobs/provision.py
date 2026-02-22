import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..k8s import (
    create_config_secret,
    create_deployment,
    create_namespace,
    create_network_policy,
    create_resource_quota,
    wait_for_pod_ready,
)
from ..niches import NICHES

logger = logging.getLogger(__name__)


async def handle_provision(payload: dict, customer_id: str, db: AsyncSession) -> None:
    """Provision a new customer box: namespace, secret, quota, netpol, deployment."""

    box_id = payload["box_id"]
    tier = payload["tier"]
    telegram_bot_token = payload["telegram_bot_token"]
    telegram_allow_from = payload.get("telegram_allow_from") or payload.get("telegram_user_id")
    model = payload.get("model", "kimi-coding/k2p5")
    thinking = payload.get("thinking", "medium")
    niche_slug = payload.get("niche")
    niche_config = NICHES.get(niche_slug) if niche_slug else None

    # 1. Register proxy token with token-proxy (it generates the token for us)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{settings.token_proxy_url}/internal/tokens",
            json={
                "customer_id": customer_id,
                "box_id": str(box_id),
            },
            headers={"X-Internal-Key": settings.internal_api_key},
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
        proxy_token = token_data["token"]

    logger.info("Registered proxy token for customer %s", customer_id)

    # 2. Create K8s namespace
    create_namespace(customer_id, tier)

    # 3. Create K8s Secret
    create_config_secret(
        customer_id,
        telegram_bot_token=telegram_bot_token,
        telegram_allow_from=str(telegram_allow_from),
        proxy_token=proxy_token,
        model=model,
        thinking=thinking,
        system_prompt=niche_config.system_prompt if niche_config else None,
    )

    # 4. Create ResourceQuota
    create_resource_quota(customer_id, tier)

    # 5. Create NetworkPolicy
    create_network_policy(customer_id)

    # 6. Create Deployment
    create_deployment(customer_id, tier, settings.openclaw_image)

    # 7. Wait for pod ready
    ready = wait_for_pod_ready(customer_id, timeout=settings.pod_ready_timeout)
    if not ready:
        raise TimeoutError(f"Pod not ready within {settings.pod_ready_timeout}s for customer {customer_id}")

    # 8. Update box status
    now = datetime.now(timezone.utc)
    await db.execute(
        text("UPDATE boxes SET status = 'active', activated_at = :now WHERE id = :box_id"),
        {"now": now, "box_id": box_id},
    )
    await db.commit()

    logger.info("Provisioned customer %s (box %s)", customer_id, box_id)
