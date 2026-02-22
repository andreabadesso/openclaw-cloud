import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock config before importing rate-limit
vi.mock("../src/config.js", () => ({
  config: {
    rateLimitRps: 10,
  },
}));

import { checkRateLimit } from "../src/rate-limit.js";

function makeRedis() {
  return {
    eval: vi.fn(),
  };
}

describe("checkRateLimit", () => {
  let redis;

  beforeEach(() => {
    redis = makeRedis();
    vi.clearAllMocks();
  });

  it("returns true when under rate limit (eval returns 1)", async () => {
    redis.eval.mockResolvedValue(1);

    const result = await checkRateLimit("cust-1", redis);
    expect(result).toBe(true);
  });

  it("returns false when over rate limit (eval returns 0)", async () => {
    redis.eval.mockResolvedValue(0);

    const result = await checkRateLimit("cust-1", redis);
    expect(result).toBe(false);
  });

  it("passes correct key format to Redis eval", async () => {
    redis.eval.mockResolvedValue(1);

    await checkRateLimit("cust-abc", redis);

    const args = redis.eval.mock.calls[0];
    // args: [script, numKeys, key, capacity, now, refillRate]
    expect(args[1]).toBe(1); // numKeys
    expect(args[2]).toBe("ratelimit:cust-abc"); // key
    expect(args[3]).toBe(10); // capacity = rateLimitRps
    expect(typeof args[4]).toBe("number"); // now in seconds
    expect(args[5]).toBe(10); // refill_rate = rateLimitRps
  });

  it("passes Lua script as first argument", async () => {
    redis.eval.mockResolvedValue(1);

    await checkRateLimit("cust-1", redis);

    const script = redis.eval.mock.calls[0][0];
    expect(script).toContain("HMGET");
    expect(script).toContain("HMSET");
    expect(script).toContain("EXPIRE");
  });

  it("uses current timestamp in seconds", async () => {
    redis.eval.mockResolvedValue(1);
    const before = Date.now() / 1000;

    await checkRateLimit("cust-1", redis);

    const after = Date.now() / 1000;
    const ts = redis.eval.mock.calls[0][4];
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it("handles different customer IDs independently", async () => {
    redis.eval.mockResolvedValueOnce(1).mockResolvedValueOnce(0);

    const r1 = await checkRateLimit("cust-1", redis);
    const r2 = await checkRateLimit("cust-2", redis);

    expect(r1).toBe(true);
    expect(r2).toBe(false);
    expect(redis.eval.mock.calls[0][2]).toBe("ratelimit:cust-1");
    expect(redis.eval.mock.calls[1][2]).toBe("ratelimit:cust-2");
  });
});
