import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..k8s import patch_config_secret, rollout_restart, wait_for_rollout
from ..providers import MCP_SERVERS

logger = logging.getLogger(__name__)


async def handle_update_connections(payload: dict, customer_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        text(
            "SELECT provider, nango_connection_id FROM customer_connections "
            "WHERE customer_id = :cid AND status = 'active'"
        ),
        {"cid": customer_id},
    )
    rows = result.fetchall()

    connections_config = json.dumps({
        "nango_proxy_url": settings.nango_server_url,
        "nango_secret_key": settings.nango_secret_key,
        "api_url": settings.api_url,
        "api_secret": settings.agent_api_secret,
        "customer_id": customer_id,
        "web_url": settings.web_url,
        "connections": [
            {
                "provider": r.provider,
                "connection_id": r.nango_connection_id,
                "mcp": MCP_SERVERS.get(r.provider),
            }
            for r in rows
        ],
    })

    patch_config_secret(customer_id, {"OPENCLAW_CONNECTIONS": connections_config})
    rollout_restart(customer_id)

    complete = wait_for_rollout(customer_id, timeout=60)
    if not complete:
        raise TimeoutError(f"Rollout not complete within 60s for customer {customer_id}")

    logger.info("Updated connections for customer %s (%d connections)", customer_id, len(rows))
