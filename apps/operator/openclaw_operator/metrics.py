"""Background collector: K8s metrics API → Postgres, hourly rollup + cleanup."""

import asyncio
import logging
import re

from kubernetes import client
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Regex to extract customer_id from namespace like "customer-<uuid>"
NS_RE = re.compile(r"^customer-(.+)$")


def parse_cpu(val: str) -> int:
    """Parse K8s CPU string to millicores. E.g. '125m' → 125, '1' → 1000."""
    if val.endswith("n"):
        return int(val[:-1]) // 1_000_000
    if val.endswith("u"):
        return int(val[:-1]) // 1_000
    if val.endswith("m"):
        return int(val[:-1])
    return int(val) * 1000


def parse_memory(val: str) -> int:
    """Parse K8s memory string to bytes. E.g. '256Mi' → 268435456."""
    units = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}
    for suffix, mult in units.items():
        if val.endswith(suffix):
            return int(val[: -len(suffix)]) * mult
    if val.endswith("k"):
        return int(val[:-1]) * 1000
    if val.endswith("M"):
        return int(val[:-1]) * 1_000_000
    if val.endswith("G"):
        return int(val[:-1]) * 1_000_000_000
    return int(val)


async def collect_pod_metrics(session_factory: async_sessionmaker[AsyncSession]) -> int:
    """Fetch pod metrics from K8s metrics API, insert snapshots. Returns count."""
    api = client.CustomObjectsApi()
    try:
        result = api.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "pods")
    except Exception as exc:
        logger.debug("metrics-server not available: %s", exc)
        return 0

    rows = []
    for item in result.get("items", []):
        ns = item["metadata"]["namespace"]
        m = NS_RE.match(ns)
        if not m:
            continue
        customer_id = m.group(1)

        for container in item.get("containers", []):
            usage = container.get("usage", {})
            cpu_str = usage.get("cpu", "0")
            mem_str = usage.get("memory", "0")
            rows.append({
                "customer_id": customer_id,
                "box_id": item["metadata"]["name"],
                "namespace": ns,
                "cpu_millicores": parse_cpu(cpu_str),
                "memory_bytes": parse_memory(mem_str),
            })

    if not rows:
        return 0

    async with session_factory() as db:
        await db.execute(
            text("""
                INSERT INTO pod_metrics_snapshots (customer_id, box_id, namespace, cpu_millicores, memory_bytes)
                VALUES (:customer_id, :box_id, :namespace, :cpu_millicores, :memory_bytes)
            """),
            rows,
        )
        await db.commit()

    return len(rows)


async def rollup_hourly(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Aggregate snapshots older than 2h into hourly buckets, then clean up."""
    async with session_factory() as db:
        # Roll up into hourly table
        await db.execute(text("""
            INSERT INTO pod_metrics_hourly (customer_id, box_id, hour, avg_cpu, max_cpu, avg_memory, max_memory, sample_count)
            SELECT
                customer_id,
                box_id,
                date_trunc('hour', collected_at) AS hour,
                avg(cpu_millicores)::int,
                max(cpu_millicores),
                avg(memory_bytes)::bigint,
                max(memory_bytes),
                count(*)::int
            FROM pod_metrics_snapshots
            WHERE collected_at < now() - interval '2 hours'
            GROUP BY customer_id, box_id, date_trunc('hour', collected_at)
            ON CONFLICT (customer_id, box_id, hour) DO UPDATE SET
                avg_cpu = EXCLUDED.avg_cpu,
                max_cpu = EXCLUDED.max_cpu,
                avg_memory = EXCLUDED.avg_memory,
                max_memory = EXCLUDED.max_memory,
                sample_count = EXCLUDED.sample_count
        """))

        # Delete rolled-up snapshots
        await db.execute(text("""
            DELETE FROM pod_metrics_snapshots
            WHERE collected_at < now() - interval '2 hours'
        """))

        # Purge old hourly data (>30 days)
        await db.execute(text("""
            DELETE FROM pod_metrics_hourly
            WHERE hour < now() - interval '30 days'
        """))

        await db.commit()
    logger.info("Hourly rollup complete")


async def metrics_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Collect metrics every 60s, roll up every ~60 ticks (~1h)."""
    logger.info("Metrics collector started")
    tick = 0
    while True:
        try:
            count = await collect_pod_metrics(session_factory)
            if count > 0:
                logger.info("Collected %d pod metric snapshots", count)

            tick += 1
            if tick >= 60:
                tick = 0
                await rollup_hourly(session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error in metrics collection")

        await asyncio.sleep(60)
