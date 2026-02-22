import { config } from "./config.js";

/**
 * Handle internal API routes for browser-proxy.
 * Protected by X-Internal-Key header.
 * @param {import("http").IncomingMessage} req
 * @param {import("http").ServerResponse} res
 * @param {import("ioredis").default} redis
 * @param {import("pg").Pool} pg
 * @returns {Promise<boolean>} true if handled
 */
export async function handleInternal(req, res, redis, pg) {
  if (!req.url.startsWith("/internal/")) return false;

  // Verify internal key
  if (!config.internalApiKey || req.headers["x-internal-key"] !== config.internalApiKey) {
    json(res, 403, { error: "Invalid internal API key" });
    return true;
  }

  // GET /internal/browser/:customer_id/sessions
  const sessionsMatch = req.url.match(/^\/internal\/browser\/([^/]+)\/sessions$/);
  if (req.method === "GET" && sessionsMatch) {
    const customerId = sessionsMatch[1];

    const { rows: active } = await pg.query(
      `SELECT COUNT(*) AS count FROM browser_sessions
       WHERE customer_id = $1 AND ended_at IS NULL`,
      [customerId],
    );

    const { rows: recent } = await pg.query(
      `SELECT id, box_id, started_at, ended_at, duration_ms
       FROM browser_sessions
       WHERE customer_id = $1
       ORDER BY started_at DESC
       LIMIT 20`,
      [customerId],
    );

    json(res, 200, {
      customer_id: customerId,
      active_sessions: Number(active[0].count),
      recent_sessions: recent,
    });
    return true;
  }

  // GET /internal/browser/:customer_id/usage
  const usageMatch = req.url.match(/^\/internal\/browser\/([^/]+)\/usage$/);
  if (req.method === "GET" && usageMatch) {
    const customerId = usageMatch[1];

    const { rows } = await pg.query(
      `SELECT COALESCE(SUM(duration_ms), 0) AS total_ms
       FROM browser_sessions
       WHERE customer_id = $1
         AND started_at >= date_trunc('month', now())`,
      [customerId],
    );

    const totalMs = Number(rows[0].total_ms);
    json(res, 200, {
      customer_id: customerId,
      total_duration_ms: totalMs,
      total_minutes: Math.round(totalMs / 60000),
      period_start: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString(),
    });
    return true;
  }

  // DELETE /internal/browser/:customer_id/sessions
  if (req.method === "DELETE" && sessionsMatch) {
    const customerId = sessionsMatch[1];

    const { rowCount } = await pg.query(
      `UPDATE browser_sessions
       SET ended_at = now(), duration_ms = EXTRACT(EPOCH FROM (now() - started_at))::integer * 1000
       WHERE customer_id = $1 AND ended_at IS NULL`,
      [customerId],
    );

    json(res, 200, {
      status: "closed",
      customer_id: customerId,
      sessions_closed: rowCount,
    });
    return true;
  }

  json(res, 404, { error: "Not found" });
  return true;
}

function json(res, status, data) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(data));
}
