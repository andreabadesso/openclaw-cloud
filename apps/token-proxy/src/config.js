import "dotenv/config";
import { getModel } from "@mariozechner/pi-ai";

const model = process.env.MODEL || "kimi-coding/k2p5";
const [provider, modelId] = model.split("/");

export const config = {
  apiKey: must("KIMI_API_KEY"),
  model: getModel(provider, modelId),
  databaseUrl: toPgUrl(must("DATABASE_URL")),
  redisUrl: process.env.REDIS_URL || "redis://localhost:6379/0",
  internalApiKey: process.env.INTERNAL_API_KEY || "",
  rateLimitRps: int("RATE_LIMIT_RPS", 10),
  usageFlushIntervalMs: int("USAGE_FLUSH_INTERVAL_MS", 5000),
  usageFlushBatchSize: int("USAGE_FLUSH_BATCH_SIZE", 100),
  port: int("PORT", 8080),
};

console.log(`Model: ${provider}/${modelId} (api: ${config.model.api}, url: ${config.model.baseUrl})`);

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
