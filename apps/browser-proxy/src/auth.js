import bcrypt from "bcrypt";

const TOKEN_CACHE_PREFIX = "browser-auth:";
const TOKEN_CACHE_TTL = 300;

/**
 * Validate a proxy token. Returns { customer_id, box_id } or null.
 * @param {string} token
 * @param {import("ioredis").default} redis
 * @param {import("pg").Pool} pg
 * @returns {Promise<{customer_id: string, box_id: string|null}|null>}
 */
export async function authenticateToken(token, redis, pg) {
  const cacheKey = `${TOKEN_CACHE_PREFIX}${token}`;

  // Check Redis cache
  const cached = await redis.get(cacheKey);
  if (cached !== null) {
    return JSON.parse(cached);
  }

  // Cache miss — query all active tokens
  const { rows } = await pg.query(
    "SELECT id, customer_id, box_id, token_hash FROM proxy_tokens WHERE revoked_at IS NULL",
  );

  for (const row of rows) {
    const match = await bcrypt.compare(token, row.token_hash);
    if (match) {
      const result = {
        customer_id: String(row.customer_id),
        box_id: row.box_id || null,
      };
      await redis.set(
        cacheKey,
        JSON.stringify(result),
        "EX",
        TOKEN_CACHE_TTL,
      );
      return result;
    }
  }

  return null;
}
