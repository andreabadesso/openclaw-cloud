import { describe, it, expect, vi, beforeEach } from "vitest";
import { checkLimits } from "../src/limits.js";

function makeRedis() {
  return {
    get: vi.fn(),
    set: vi.fn(),
  };
}

function makePg() {
  return {
    query: vi.fn(),
  };
}

describe("checkLimits", () => {
  let redis, pg;

  beforeEach(() => {
    redis = makeRedis();
    pg = makePg();
    vi.clearAllMocks();
  });

  it("returns allowed=true when under limit (from cache)", async () => {
    redis.get.mockResolvedValue(JSON.stringify({ used: 500, limit: 1000, tier: "starter" }));

    const result = await checkLimits("cust-1", redis, pg);
    expect(result).toEqual({
      allowed: true,
      warning: false,
      used: 500,
      limit: 1000,
      tier: "starter",
    });
    expect(redis.get).toHaveBeenCalledWith("limit:cust-1");
    expect(pg.query).not.toHaveBeenCalled();
  });

  it("returns allowed=false when at limit", async () => {
    redis.get.mockResolvedValue(JSON.stringify({ used: 1000, limit: 1000, tier: "starter" }));

    const result = await checkLimits("cust-1", redis, pg);
    expect(result.allowed).toBe(false);
  });

  it("returns allowed=false when over limit", async () => {
    redis.get.mockResolvedValue(JSON.stringify({ used: 1500, limit: 1000, tier: "starter" }));

    const result = await checkLimits("cust-1", redis, pg);
    expect(result.allowed).toBe(false);
  });

  it("returns warning=true when at 90% usage", async () => {
    redis.get.mockResolvedValue(JSON.stringify({ used: 900, limit: 1000, tier: "starter" }));

    const result = await checkLimits("cust-1", redis, pg);
    expect(result.allowed).toBe(true);
    expect(result.warning).toBe(true);
  });

  it("returns warning=false when below 90%", async () => {
    redis.get.mockResolvedValue(JSON.stringify({ used: 899, limit: 1000, tier: "starter" }));

    const result = await checkLimits("cust-1", redis, pg);
    expect(result.warning).toBe(false);
  });

  it("falls back to DB on cache miss and caches the result", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({
      rows: [{ tokens_used: 200, tokens_limit: 5000, tier: "pro" }],
    });

    const result = await checkLimits("cust-1", redis, pg);
    expect(result).toEqual({
      allowed: true,
      warning: false,
      used: 200,
      limit: 5000,
      tier: "pro",
    });
    expect(redis.set).toHaveBeenCalledWith(
      "limit:cust-1",
      JSON.stringify({ used: 200, limit: 5000, tier: "pro" }),
      "EX",
      60,
    );
  });

  it("returns allowed=false with zeros when no DB rows", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({ rows: [] });

    const result = await checkLimits("cust-1", redis, pg);
    expect(result).toEqual({
      allowed: false,
      warning: false,
      used: 0,
      limit: 0,
      tier: "unknown",
    });
    expect(redis.set).not.toHaveBeenCalled();
  });

  it("converts DB values to numbers/strings", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({
      rows: [{ tokens_used: "300", tokens_limit: "10000", tier: "enterprise" }],
    });

    const result = await checkLimits("cust-1", redis, pg);
    expect(result.used).toBe(300);
    expect(result.limit).toBe(10000);
    expect(result.tier).toBe("enterprise");
    expect(typeof result.used).toBe("number");
    expect(typeof result.limit).toBe("number");
    expect(typeof result.tier).toBe("string");
  });

  it("queries DB with correct SQL and customer_id parameter", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({ rows: [] });

    await checkLimits("cust-42", redis, pg);

    expect(pg.query).toHaveBeenCalledTimes(1);
    const [sql, params] = pg.query.mock.calls[0];
    expect(sql).toContain("usage_monthly");
    expect(sql).toContain("subscriptions");
    expect(params).toEqual(["cust-42"]);
  });
});
