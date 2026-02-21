import bcrypt from "bcrypt";

const TOKEN_CACHE_PREFIX = "proxy_token:";
const TOKEN_CACHE_TTL = 300;

/**
 * Validate a proxy token. Returns customer_id or null.
 * @param {string} token
 * @param {import("ioredis").default} redis
 * @param {import("pg").Pool} pg
 * @returns {Promise<string|null>}
 */
export async function authenticateToken(token, redis, pg) {
  const cacheKey = `${TOKEN_CACHE_PREFIX}${token}`;

  // Check Redis cache
  const cached = await redis.get(cacheKey);
  if (cached !== null) {
    return JSON.parse(cached).customer_id;
  }

  // Cache miss — query all active tokens
  const { rows } = await pg.query(
    "SELECT id, customer_id, token_hash FROM proxy_tokens WHERE revoked_at IS NULL",
  );

  for (const row of rows) {
    const match = await bcrypt.compare(token, row.token_hash);
    if (match) {
      await redis.set(
        cacheKey,
        JSON.stringify({
          customer_id: String(row.customer_id),
          token_id: String(row.id),
        }),
        "EX",
        TOKEN_CACHE_TTL,
      );
      return String(row.customer_id);
    }
  }

  return null;
}
