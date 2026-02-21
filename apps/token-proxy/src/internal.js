import crypto from "node:crypto";
import bcrypt from "bcrypt";
import { config } from "./config.js";

const TOKEN_CACHE_PREFIX = "proxy_token:";

/**
 * Handle internal API routes.
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

  // POST /internal/tokens
  if (req.method === "POST" && req.url === "/internal/tokens") {
    const body = await readBody(req);
    const { customer_id, box_id } = JSON.parse(body);

    const rawToken = crypto.randomBytes(16).toString("hex"); // 32 hex chars
    const tokenHash = await bcrypt.hash(rawToken, 10);
    const tokenId = crypto.randomUUID();

    await pg.query(
      "INSERT INTO proxy_tokens (id, customer_id, box_id, token_hash) VALUES ($1, $2, $3, $4)",
      [tokenId, customer_id, box_id, tokenHash],
    );

    // Pre-warm cache
    await redis.set(
      `${TOKEN_CACHE_PREFIX}${rawToken}`,
      JSON.stringify({ customer_id, token_id: tokenId }),
      "EX",
      300,
    );

    json(res, 200, { token_id: tokenId, token: rawToken });
    return true;
  }

  // DELETE /internal/tokens/:id
  const deleteMatch = req.url.match(/^\/internal\/tokens\/([^/]+)$/);
  if (req.method === "DELETE" && deleteMatch) {
    const tokenId = deleteMatch[1];
    // Don't match the usage endpoint
    if (req.url.includes("/usage")) return false;

    const { rows } = await pg.query(
      "UPDATE proxy_tokens SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL RETURNING customer_id",
      [tokenId],
    );

    if (rows.length === 0) {
      json(res, 404, { error: "Token not found or already revoked" });
    } else {
      json(res, 200, { status: "revoked", token_id: tokenId });
    }
    return true;
  }

  // GET /internal/tokens/:customer_id/usage
  const usageMatch = req.url.match(/^\/internal\/tokens\/([^/]+)\/usage$/);
  if (req.method === "GET" && usageMatch) {
    const customerId = usageMatch[1];

    const { rows } = await pg.query(
      `SELECT tokens_used, tokens_limit, period_start, period_end
       FROM usage_monthly
       WHERE customer_id = $1
         AND period_start <= now()
         AND period_end > now()
       ORDER BY period_start DESC LIMIT 1`,
      [customerId],
    );

    if (rows.length === 0) {
      json(res, 404, { error: "No usage record found" });
    } else {
      json(res, 200, {
        customer_id: customerId,
        tokens_used: Number(rows[0].tokens_used),
        tokens_limit: Number(rows[0].tokens_limit),
        period_start: String(rows[0].period_start),
        period_end: String(rows[0].period_end),
      });
    }
    return true;
  }

  json(res, 404, { error: "Not found" });
  return true;
}

function json(res, status, data) {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(data));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
    req.on("error", reject);
  });
}
