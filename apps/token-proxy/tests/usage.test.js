import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../src/config.js", () => ({
  config: {
    usageFlushIntervalMs: 100,
    usageFlushBatchSize: 5,
  },
}));

import { pushUsageEvent } from "../src/usage.js";

function makeRedis() {
  return {
    xadd: vi.fn(),
    xgroup: vi.fn(),
    xreadgroup: vi.fn(),
    xack: vi.fn(),
    get: vi.fn(),
    set: vi.fn(),
    ttl: vi.fn(),
  };
}

describe("pushUsageEvent", () => {
  let redis;

  beforeEach(() => {
    redis = makeRedis();
    vi.clearAllMocks();
  });

  it("pushes event to Redis stream with correct fields", async () => {
    redis.xadd.mockResolvedValue("1234567890-0");

    await pushUsageEvent(redis, {
      customer_id: "cust-1",
      box_id: "box-1",
      model: "gpt-4o",
      prompt_tokens: 100,
      completion_tokens: 50,
      request_id: "req-1",
    });

    expect(redis.xadd).toHaveBeenCalledWith(
      "usage:events",
      "*",
      "customer_id", "cust-1",
      "box_id", "box-1",
      "model", "gpt-4o",
      "prompt_tokens", "100",
      "completion_tokens", "50",
      "request_id", "req-1",
      "timestamp", expect.any(String),
    );
  });

  it("uses empty string for null box_id", async () => {
    redis.xadd.mockResolvedValue("1234567890-0");

    await pushUsageEvent(redis, {
      customer_id: "cust-1",
      box_id: null,
      model: "gpt-4o",
      prompt_tokens: 10,
      completion_tokens: 5,
      request_id: "req-2",
    });

    const args = redis.xadd.mock.calls[0];
    // box_id is at index 5 (after stream, *, customer_id, value)
    const boxIdIdx = args.indexOf("box_id");
    expect(args[boxIdIdx + 1]).toBe("");
  });

  it("converts token counts to strings", async () => {
    redis.xadd.mockResolvedValue("ok");

    await pushUsageEvent(redis, {
      customer_id: "c1",
      model: "m1",
      prompt_tokens: 0,
      completion_tokens: 0,
      request_id: "r1",
    });

    const args = redis.xadd.mock.calls[0];
    const promptIdx = args.indexOf("prompt_tokens");
    expect(args[promptIdx + 1]).toBe("0");
    const compIdx = args.indexOf("completion_tokens");
    expect(args[compIdx + 1]).toBe("0");
  });

  it("adds timestamp in seconds", async () => {
    redis.xadd.mockResolvedValue("ok");
    const before = Date.now() / 1000;

    await pushUsageEvent(redis, {
      customer_id: "c1",
      model: "m1",
      prompt_tokens: 1,
      completion_tokens: 1,
      request_id: "r1",
    });

    const after = Date.now() / 1000;
    const args = redis.xadd.mock.calls[0];
    const tsIdx = args.indexOf("timestamp");
    const ts = parseFloat(args[tsIdx + 1]);
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });
});
