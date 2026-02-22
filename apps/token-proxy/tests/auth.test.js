import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock bcrypt
vi.mock("bcrypt", () => ({
  default: {
    compare: vi.fn(),
  },
}));

import bcrypt from "bcrypt";
import { authenticateToken } from "../src/auth.js";

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

describe("authenticateToken", () => {
  let redis, pg;

  beforeEach(() => {
    redis = makeRedis();
    pg = makePg();
    vi.clearAllMocks();
  });

  it("returns customer_id from cache hit", async () => {
    redis.get.mockResolvedValue(JSON.stringify({ customer_id: "cust-123", token_id: "tok-1" }));

    const result = await authenticateToken("my-token", redis, pg);
    expect(result).toBe("cust-123");
    expect(redis.get).toHaveBeenCalledWith("proxy_token:my-token");
    expect(pg.query).not.toHaveBeenCalled();
  });

  it("returns null for invalid token (no DB match)", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({
      rows: [{ id: "tok-1", customer_id: "cust-1", token_hash: "$2b$10$hash1" }],
    });
    bcrypt.compare.mockResolvedValue(false);

    const result = await authenticateToken("bad-token", redis, pg);
    expect(result).toBeNull();
    expect(pg.query).toHaveBeenCalledWith(
      "SELECT id, customer_id, token_hash FROM proxy_tokens WHERE revoked_at IS NULL",
    );
  });

  it("returns customer_id on valid token from DB and caches it", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({
      rows: [
        { id: "tok-1", customer_id: "cust-1", token_hash: "$2b$10$hash1" },
        { id: "tok-2", customer_id: "cust-2", token_hash: "$2b$10$hash2" },
      ],
    });
    // First token doesn't match, second does
    bcrypt.compare.mockResolvedValueOnce(false).mockResolvedValueOnce(true);

    const result = await authenticateToken("valid-token", redis, pg);
    expect(result).toBe("cust-2");
    expect(redis.set).toHaveBeenCalledWith(
      "proxy_token:valid-token",
      JSON.stringify({ customer_id: "cust-2", token_id: "tok-2" }),
      "EX",
      300,
    );
  });

  it("returns null when no active tokens exist in DB", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({ rows: [] });

    const result = await authenticateToken("any-token", redis, pg);
    expect(result).toBeNull();
  });

  it("converts customer_id to string", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({
      rows: [{ id: 42, customer_id: 123, token_hash: "$2b$10$hash" }],
    });
    bcrypt.compare.mockResolvedValue(true);

    const result = await authenticateToken("tok", redis, pg);
    expect(result).toBe("123");
    const cached = JSON.parse(redis.set.mock.calls[0][1]);
    expect(cached.customer_id).toBe("123");
    expect(cached.token_id).toBe("42");
  });

  it("matches first valid token and stops iterating", async () => {
    redis.get.mockResolvedValue(null);
    pg.query.mockResolvedValue({
      rows: [
        { id: "tok-1", customer_id: "cust-1", token_hash: "$2b$10$hash1" },
        { id: "tok-2", customer_id: "cust-2", token_hash: "$2b$10$hash2" },
        { id: "tok-3", customer_id: "cust-3", token_hash: "$2b$10$hash3" },
      ],
    });
    bcrypt.compare.mockResolvedValueOnce(true);

    const result = await authenticateToken("tok", redis, pg);
    expect(result).toBe("cust-1");
    // Only compared once since first match was found
    expect(bcrypt.compare).toHaveBeenCalledTimes(1);
  });
});
