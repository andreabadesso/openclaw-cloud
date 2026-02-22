import "dotenv/config";

export const config = {
  browserlessUrl: must("BROWSERLESS_URL"),
  databaseUrl: toPgUrl(must("DATABASE_URL")),
  redisUrl: process.env.REDIS_URL || "redis://localhost:6379/0",
  internalApiKey: process.env.INTERNAL_API_KEY || "",
  port: int("PORT", 9223),
  maxConcurrentSessions: int("MAX_CONCURRENT_SESSIONS", 2),
  maxSessionDurationMs: int("MAX_SESSION_DURATION_MS", 600000),
  usageFlushIntervalMs: int("USAGE_FLUSH_INTERVAL_MS", 5000),
  usageFlushBatchSize: int("USAGE_FLUSH_BATCH_SIZE", 100),
};

function must(name) {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function int(name, fallback) {
  const v = process.env[name];
  return v ? parseInt(v, 10) : fallback;
}

/** Convert asyncpg-style URL to pg-compatible URL */
function toPgUrl(url) {
  return url
    .replace("postgresql+asyncpg://", "postgresql://")
    .replace("postgres+asyncpg://", "postgresql://");
}
