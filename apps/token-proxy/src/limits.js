const LIMIT_CACHE_PREFIX = "limit:";
const LIMIT_CACHE_TTL = 60;

/**
 * Check token usage limits.
 * @param {string} customerId
 * @param {import("ioredis").default} redis
 * @param {import("pg").Pool} pg
 * @returns {Promise<{allowed: boolean, warning: boolean, used: number, limit: number, tier: string}>}
 */
export async function checkLimits(customerId, redis, pg) {
  const cacheKey = `${LIMIT_CACHE_PREFIX}${customerId}`;

  const cached = await redis.get(cacheKey);
  let used, limit, tier;

  if (cached !== null) {
    const data = JSON.parse(cached);
    used = data.used;
    limit = data.limit;
    tier = data.tier;
  } else {
    const { rows } = await pg.query(
      `SELECT um.tokens_used, um.tokens_limit, s.tier
       FROM usage_monthly um
       JOIN subscriptions s ON s.customer_id = um.customer_id
       WHERE um.customer_id = $1
         AND um.period_start <= now()
         AND um.period_end > now()
         AND s.status = 'active'`,
      [customerId],
    );

    if (rows.length === 0) {
      return { allowed: false, warning: false, used: 0, limit: 0, tier: "unknown" };
    }

    used = Number(rows[0].tokens_used);
    limit = Number(rows[0].tokens_limit);
    tier = String(rows[0].tier);

    await redis.set(
      cacheKey,
      JSON.stringify({ used, limit, tier }),
      "EX",
      LIMIT_CACHE_TTL,
    );
  }

  return {
    allowed: used < limit,
    warning: used >= Math.floor(limit * 0.9),
    used,
    limit,
    tier,
  };
}
