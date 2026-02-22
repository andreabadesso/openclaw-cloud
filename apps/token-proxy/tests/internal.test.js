import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock bcrypt
vi.mock("bcrypt", () => ({
  default: {
    hash: vi.fn().mockResolvedValue("$2b$10$hashed"),
  },
}));

// Mock config
vi.mock("../src/config.js", () => ({
  config: {
    internalApiKey: "secret-internal-key",
  },
}));

// Mock crypto for deterministic token generation
vi.mock("node:crypto", () => ({
  default: {
    randomBytes: vi.fn(() => ({
      toString: vi.fn(() => "abcdef1234567890abcdef1234567890"),
    })),
    randomUUID: vi.fn(() => "550e8400-e29b-41d4-a716-446655440000"),
  },
}));

import { handleInternal } from "../src/internal.js";

function makeReq(method, url, headers = {}, body = "") {
  const req = {
    method,
    url,
    headers: { "x-internal-key": "secret-internal-key", ...headers },
    on: vi.fn((event, cb) => {
      if (event === "data" && body) {
        cb(Buffer.from(body));
      }
      if (event === "end") {
        cb();
      }
    }),
  };
  return req;
}

function makeRes() {
  const res = {
    statusCode: null,
    body: null,
    writeHead: vi.fn((status) => {
      res.statusCode = status;
    }),
    end: vi.fn((data) => {
      res.body = data ? JSON.parse(data) : null;
    }),
  };
  return res;
}

function makeRedis() {
  return {
    set: vi.fn(),
  };
}

function makePg() {
  return {
    query: vi.fn(),
  };
}

describe("handleInternal", () => {
  let redis, pg;

  beforeEach(() => {
    redis = makeRedis();
    pg = makePg();
    vi.clearAllMocks();
  });

  describe("authentication", () => {
    it("rejects requests without internal API key", async () => {
      const req = makeReq("POST", "/internal/tokens", { "x-internal-key": "wrong-key" });
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(403);
      expect(res.body.error).toBe("Invalid internal API key");
    });

    it("rejects requests with missing internal API key header", async () => {
      const req = makeReq("POST", "/internal/tokens", {});
      delete req.headers["x-internal-key"];
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(403);
    });
  });

  describe("POST /internal/tokens - register token", () => {
    it("creates a new token and returns it", async () => {
      pg.query.mockResolvedValue({});
      const req = makeReq("POST", "/internal/tokens", {}, JSON.stringify({ customer_id: "cust-1", box_id: "box-1" }));
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(200);
      expect(res.body.token_id).toBe("550e8400-e29b-41d4-a716-446655440000");
      expect(res.body.token).toBe("abcdef1234567890abcdef1234567890");
    });

    it("inserts token hash into database", async () => {
      pg.query.mockResolvedValue({});
      const req = makeReq("POST", "/internal/tokens", {}, JSON.stringify({ customer_id: "cust-1", box_id: "box-1" }));
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(pg.query).toHaveBeenCalledWith(
        "INSERT INTO proxy_tokens (id, customer_id, box_id, token_hash) VALUES ($1, $2, $3, $4)",
        ["550e8400-e29b-41d4-a716-446655440000", "cust-1", "box-1", "$2b$10$hashed"],
      );
    });

    it("pre-warms Redis cache", async () => {
      pg.query.mockResolvedValue({});
      const req = makeReq("POST", "/internal/tokens", {}, JSON.stringify({ customer_id: "cust-1", box_id: "box-1" }));
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(redis.set).toHaveBeenCalledWith(
        "proxy_token:abcdef1234567890abcdef1234567890",
        JSON.stringify({ customer_id: "cust-1", token_id: "550e8400-e29b-41d4-a716-446655440000" }),
        "EX",
        300,
      );
    });
  });

  describe("DELETE /internal/tokens/:id - revoke token", () => {
    it("revokes an existing token", async () => {
      pg.query.mockResolvedValue({ rows: [{ customer_id: "cust-1" }] });
      const req = makeReq("DELETE", "/internal/tokens/tok-123");
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(200);
      expect(res.body.status).toBe("revoked");
      expect(res.body.token_id).toBe("tok-123");
      expect(pg.query).toHaveBeenCalledWith(
        "UPDATE proxy_tokens SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL RETURNING customer_id",
        ["tok-123"],
      );
    });

    it("returns 404 for non-existent or already revoked token", async () => {
      pg.query.mockResolvedValue({ rows: [] });
      const req = makeReq("DELETE", "/internal/tokens/tok-missing");
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(404);
      expect(res.body.error).toBe("Token not found or already revoked");
    });
  });

  describe("GET /internal/tokens/:customer_id/usage", () => {
    it("returns current period usage", async () => {
      pg.query.mockResolvedValue({
        rows: [{
          tokens_used: "5000",
          tokens_limit: "100000",
          period_start: "2026-02-01T00:00:00Z",
          period_end: "2026-03-01T00:00:00Z",
        }],
      });
      const req = makeReq("GET", "/internal/tokens/cust-1/usage");
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(200);
      expect(res.body.customer_id).toBe("cust-1");
      expect(res.body.tokens_used).toBe(5000);
      expect(res.body.tokens_limit).toBe(100000);
    });

    it("returns 404 when no usage record exists", async () => {
      pg.query.mockResolvedValue({ rows: [] });
      const req = makeReq("GET", "/internal/tokens/cust-new/usage");
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(404);
      expect(res.body.error).toBe("No usage record found");
    });
  });

  describe("unknown routes", () => {
    it("returns 404 for unknown internal routes", async () => {
      const req = makeReq("GET", "/internal/unknown");
      const res = makeRes();

      await handleInternal(req, res, redis, pg);

      expect(res.statusCode).toBe(404);
      expect(res.body.error).toBe("Not found");
    });

    it("returns false for non-internal routes", async () => {
      const req = makeReq("GET", "/health");
      const res = makeRes();

      const result = await handleInternal(req, res, redis, pg);
      expect(result).toBe(false);
    });
  });
});
