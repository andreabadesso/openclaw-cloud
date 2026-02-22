import { describe, it, expect, vi, beforeEach } from "vitest";

// We test config by manipulating process.env before dynamic import
describe("config", () => {
  const originalEnv = { ...process.env };

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  function setRequiredEnv(overrides = {}) {
    process.env.KIMI_API_KEY = "test-api-key";
    process.env.DATABASE_URL = "postgresql://user:pass@localhost:5432/db";
    process.env.MODEL = "openai/gpt-4o";
    Object.assign(process.env, overrides);
  }

  it("throws when KIMI_API_KEY is missing", async () => {
    process.env.DATABASE_URL = "postgresql://user:pass@localhost:5432/db";
    process.env.MODEL = "openai/gpt-4o";
    delete process.env.KIMI_API_KEY;
    await expect(() => import("../src/config.js")).rejects.toThrow("Missing required env var: KIMI_API_KEY");
  });

  it("throws when DATABASE_URL is missing", async () => {
    process.env.KIMI_API_KEY = "test-key";
    process.env.MODEL = "openai/gpt-4o";
    delete process.env.DATABASE_URL;
    await expect(() => import("../src/config.js")).rejects.toThrow("Missing required env var: DATABASE_URL");
  });

  it("loads config with defaults", async () => {
    setRequiredEnv();
    const { config } = await import("../src/config.js");
    expect(config.apiKey).toBe("test-api-key");
    expect(config.redisUrl).toBe("redis://localhost:6379/0");
    expect(config.rateLimitRps).toBe(10);
    expect(config.usageFlushIntervalMs).toBe(5000);
    expect(config.usageFlushBatchSize).toBe(100);
    expect(config.port).toBe(8080);
  });

  it("uses custom values from env", async () => {
    setRequiredEnv({
      REDIS_URL: "redis://custom:6380/1",
      INTERNAL_API_KEY: "my-internal-key",
      RATE_LIMIT_RPS: "20",
      USAGE_FLUSH_INTERVAL_MS: "10000",
      USAGE_FLUSH_BATCH_SIZE: "50",
      PORT: "9090",
    });
    const { config } = await import("../src/config.js");
    expect(config.redisUrl).toBe("redis://custom:6380/1");
    expect(config.internalApiKey).toBe("my-internal-key");
    expect(config.rateLimitRps).toBe(20);
    expect(config.usageFlushIntervalMs).toBe(10000);
    expect(config.usageFlushBatchSize).toBe(50);
    expect(config.port).toBe(9090);
  });

  it("converts asyncpg-style DATABASE_URL to pg format", async () => {
    setRequiredEnv({ DATABASE_URL: "postgresql+asyncpg://user:pass@host:5432/db" });
    const { config } = await import("../src/config.js");
    expect(config.databaseUrl).toBe("postgresql://user:pass@host:5432/db");
  });

  it("converts postgres+asyncpg:// to postgresql://", async () => {
    setRequiredEnv({ DATABASE_URL: "postgres+asyncpg://user:pass@host:5432/db" });
    const { config } = await import("../src/config.js");
    expect(config.databaseUrl).toBe("postgresql://user:pass@host:5432/db");
  });
});
