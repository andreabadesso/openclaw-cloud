/**
 * Integration tests for the browser-proxy service.
 *
 * Strategy: spin up a mock "browserless" WS+HTTP server, set env vars,
 * mock pg/ioredis/bcrypt, then import server.js (which auto-starts).
 * PORT=0 gives us an ephemeral port we read from server.address().
 */
import { jest, describe, it, expect, beforeAll, afterAll, afterEach } from "@jest/globals";
import http from "node:http";
import { WebSocketServer, WebSocket } from "ws";

// ---------------------------------------------------------------------------
// 1. Create mock "browserless" server BEFORE setting env vars
// ---------------------------------------------------------------------------

let mockBrowserless;
let mockBrowserlessPort;

async function startMockBrowserless() {
  const wss = new WebSocketServer({ noServer: true });
  const server = http.createServer((req, res) => {
    if (req.url.startsWith("/json/version")) {
      const body = JSON.stringify({
        webSocketDebuggerUrl: `ws://127.0.0.1:${mockBrowserlessPort}/devtools/browser/FAKE-UUID`,
      });
      res.writeHead(200, { "content-type": "application/json" });
      res.end(body);
      return;
    }
    if (req.url.startsWith("/json")) {
      const body = JSON.stringify([
        {
          webSocketDebuggerUrl: `ws://127.0.0.1:${mockBrowserlessPort}/devtools/page/PAGE-1`,
          title: "Mock Page",
        },
      ]);
      res.writeHead(200, { "content-type": "application/json" });
      res.end(body);
      return;
    }
    res.writeHead(404);
    res.end();
  });

  server.on("upgrade", (req, socket, head) => {
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit("connection", ws, req);
    });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  mockBrowserlessPort = server.address().port;
  return { server, wss };
}

// ---------------------------------------------------------------------------
// 2. Set env vars BEFORE any source imports
// ---------------------------------------------------------------------------

process.env.BROWSERLESS_URL = "http://127.0.0.1:19999?token=test-token";
process.env.DATABASE_URL = "postgres://localhost:5432/test";
process.env.REDIS_URL = "redis://localhost:6379/0";
process.env.PORT = "0";
process.env.MAX_CONCURRENT_SESSIONS = "2";
process.env.MAX_SESSION_DURATION_MS = "600000";
process.env.INTERNAL_API_KEY = "test-internal";

// ---------------------------------------------------------------------------
// 3. Mock external dependencies
// ---------------------------------------------------------------------------

const mockQuery = jest.fn().mockResolvedValue({ rows: [] });
const mockConnect = jest.fn().mockResolvedValue({
  query: mockQuery,
  release: jest.fn(),
});
const mockPool = { query: mockQuery, connect: mockConnect, end: jest.fn() };

jest.unstable_mockModule("pg", () => ({
  default: { Pool: jest.fn(() => mockPool) },
  Pool: jest.fn(() => mockPool),
}));

const redisStore = new Map();
const mockRedis = {
  get: jest.fn((key) => Promise.resolve(redisStore.get(key) ?? null)),
  set: jest.fn((...args) => {
    redisStore.set(args[0], args[1]);
    return Promise.resolve("OK");
  }),
  setex: jest.fn((key, _ttl, val) => { redisStore.set(key, val); return Promise.resolve("OK"); }),
  del: jest.fn((key) => { redisStore.delete(key); return Promise.resolve(1); }),
  xadd: jest.fn().mockResolvedValue("mock-id"),
  // xreadgroup must block like real Redis BLOCK to prevent OOM from infinite spin
  xreadgroup: jest.fn(() => new Promise((resolve) => setTimeout(() => resolve(null), 60000))),
  xgroup: jest.fn().mockResolvedValue("OK"),
  xack: jest.fn().mockResolvedValue(1),
  quit: jest.fn(),
  disconnect: jest.fn(),
  on: jest.fn(),
  status: "ready",
};

jest.unstable_mockModule("ioredis", () => ({
  default: jest.fn(() => mockRedis),
}));

jest.unstable_mockModule("bcrypt", () => ({
  default: {
    compare: jest.fn((plain, hash) =>
      Promise.resolve(plain === hash || hash === "valid-hash")
    ),
  },
}));

// ---------------------------------------------------------------------------
// 4. Helpers
// ---------------------------------------------------------------------------

function httpGet(port, path, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = http.get({ hostname: "127.0.0.1", port, path, headers }, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => resolve({ status: res.statusCode, headers: res.headers, body: data }));
    });
    req.on("error", reject);
  });
}

function connectWs(port, path, headers = {}) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}${path}`, { headers });
    ws.on("open", () => resolve(ws));
    ws.on("error", reject);
    ws.on("unexpected-response", (_req, res) => {
      resolve({ rejected: true, status: res.statusCode });
    });
  });
}

function waitForMessage(ws) {
  return new Promise((resolve) => {
    ws.once("message", (data) => resolve(data.toString()));
  });
}

function waitForClose(ws) {
  return new Promise((resolve) => {
    ws.once("close", (code, reason) => resolve({ code, reason: reason?.toString() }));
  });
}

// ---------------------------------------------------------------------------
// 5. Tests
// ---------------------------------------------------------------------------

describe("browser-proxy", () => {
  let proxyServer;
  let proxyPort;
  let sessionModule;

  beforeAll(async () => {
    // Start mock browserless
    mockBrowserless = await startMockBrowserless();

    // Update env var with real port BEFORE importing server.js
    process.env.BROWSERLESS_URL = `http://127.0.0.1:${mockBrowserlessPort}?token=test-token`;

    // Set up pg mock to return valid token for auth
    mockQuery.mockImplementation((sql) => {
      if (typeof sql === "string" && sql.includes("proxy_tokens")) {
        return Promise.resolve({
          rows: [{ token_hash: "valid-hash", customer_id: "cust-123", box_id: "box-1" }],
        });
      }
      return Promise.resolve({ rows: [] });
    });

    // Import session module so we can clean up between tests
    sessionModule = await import("../src/session.js");

    // Import server.js (auto-starts on PORT=0)
    const mod = await import("../src/server.js");
    proxyServer = mod.server;

    // Wait for server to be listening
    await new Promise((resolve) => {
      if (proxyServer.listening) return resolve();
      proxyServer.on("listening", resolve);
    });
    proxyPort = proxyServer.address().port;
  }, 15000);

  afterAll(async () => {
    // Force-close all sessions first
    if (sessionModule) {
      for (const session of sessionModule.listSessions()) {
        sessionModule.closeSession(session.id);
      }
    }
    // Close all mock browserless WS connections
    if (mockBrowserless?.wss) {
      for (const ws of mockBrowserless.wss.clients) {
        ws.terminate();
      }
    }
    // Close servers (use short timeout to not hang)
    if (proxyServer) {
      proxyServer.close();
    }
    if (mockBrowserless?.server) {
      mockBrowserless.server.close();
    }
    await new Promise((r) => setTimeout(r, 200));
  }, 5000);

  afterEach(async () => {
    // Remove all connection listeners on mock browserless
    mockBrowserless.wss.removeAllListeners("connection");
    // Clear redis auth cache
    redisStore.clear();
    // Force-close all active sessions to prevent leakage between tests
    if (sessionModule) {
      for (const session of sessionModule.listSessions()) {
        sessionModule.closeSession(session.id);
      }
    }
    // Give time for close events to propagate
    await new Promise((r) => setTimeout(r, 100));
  });

  // -----------------------------------------------------------------------
  // Health check
  // -----------------------------------------------------------------------
  describe("GET /health", () => {
    it("returns 200 OK", async () => {
      const res = await httpGet(proxyPort, "/health");
      expect(res.status).toBe(200);
      const body = JSON.parse(res.body);
      expect(body.status).toBe("ok");
    });
  });

  // -----------------------------------------------------------------------
  // URL rewriting
  // -----------------------------------------------------------------------
  describe("URL rewriting", () => {
    it("rewrites webSocketDebuggerUrl in /json/version", async () => {
      const res = await httpGet(proxyPort, "/json/version");
      expect(res.status).toBe(200);
      const body = JSON.parse(res.body);
      expect(body.webSocketDebuggerUrl).not.toContain(String(mockBrowserlessPort));
      expect(body.webSocketDebuggerUrl).toContain(String(proxyPort));
      expect(body.webSocketDebuggerUrl).not.toContain("token=");
    });

    it("rewrites webSocketDebuggerUrl in /json/list", async () => {
      const res = await httpGet(proxyPort, "/json");
      expect(res.status).toBe(200);
      const body = JSON.parse(res.body);
      expect(Array.isArray(body)).toBe(true);
      expect(body[0].webSocketDebuggerUrl).toContain(String(proxyPort));
      expect(body[0].webSocketDebuggerUrl).not.toContain("token=");
    });
  });

  // -----------------------------------------------------------------------
  // WebSocket proxy — bidirectional
  // -----------------------------------------------------------------------
  describe("WebSocket proxy flow", () => {
    it("forwards messages bidirectionally", async () => {
      mockBrowserless.wss.on("connection", (ws) => {
        ws.on("message", (data) => ws.send(`echo:${data}`));
      });

      const client = await connectWs(proxyPort, "/devtools/browser/FAKE-UUID", {
        authorization: "Bearer valid-token",
      });

      const msgPromise = waitForMessage(client);
      client.send("hello");
      const reply = await msgPromise;
      expect(reply).toBe("echo:hello");

      client.close();
      await new Promise((r) => setTimeout(r, 100));
    });

    it("forwards upstream messages to client", async () => {
      mockBrowserless.wss.on("connection", (ws) => {
        // Small delay so the proxy finishes wiring up the message handlers
        // before upstream sends (race condition: handleUpgrade is async)
        setTimeout(() => ws.send("server-push"), 50);
      });

      const client = await connectWs(proxyPort, "/devtools/browser/FAKE-UUID", {
        authorization: "Bearer valid-token",
      });

      const msg = await waitForMessage(client);
      expect(msg).toBe("server-push");

      client.close();
      await new Promise((r) => setTimeout(r, 100));
    }, 10000);
  });

  // -----------------------------------------------------------------------
  // Auth rejection
  // -----------------------------------------------------------------------
  describe("auth rejection", () => {
    it("rejects WS upgrade with no auth header", async () => {
      const result = await connectWs(proxyPort, "/devtools/browser/FAKE-UUID", {});
      expect(result.rejected).toBe(true);
      expect(result.status).toBe(401);
    });

    it("rejects WS upgrade with invalid token", async () => {
      // Override pg mock to return no rows for this request
      mockQuery.mockImplementationOnce(() =>
        Promise.resolve({ rows: [] })
      );

      const result = await connectWs(proxyPort, "/devtools/browser/FAKE-UUID", {
        authorization: "Bearer bad-token",
      });
      expect(result.rejected).toBe(true);
      expect(result.status).toBe(401);
    });
  });

  // -----------------------------------------------------------------------
  // Session limits
  // -----------------------------------------------------------------------
  describe("session limits", () => {
    it("returns 429 when max concurrent sessions exceeded", async () => {
      // MAX_CONCURRENT_SESSIONS is 2
      mockBrowserless.wss.on("connection", (ws) => {
        ws.on("message", (d) => ws.send(d));
      });

      // Verify we start with 0 sessions
      expect(sessionModule.listSessions()).toHaveLength(0);

      const client1 = await connectWs(proxyPort, "/devtools/browser/UUID-1", {
        authorization: "Bearer valid-token",
      });
      expect(client1.rejected).toBeUndefined();

      const client2 = await connectWs(proxyPort, "/devtools/browser/UUID-2", {
        authorization: "Bearer valid-token",
      });
      expect(client2.rejected).toBeUndefined();

      // Third connection should be rejected with 429
      const result = await connectWs(proxyPort, "/devtools/browser/UUID-3", {
        authorization: "Bearer valid-token",
      });
      expect(result.rejected).toBe(true);
      expect(result.status).toBe(429);

      // Cleanup handled by afterEach
    }, 10000);
  });

  // -----------------------------------------------------------------------
  // Session cleanup
  // -----------------------------------------------------------------------
  describe("session cleanup", () => {
    it("closes upstream when downstream closes", async () => {
      let upstreamWs;
      const upstreamConnected = new Promise((resolve) => {
        mockBrowserless.wss.on("connection", (ws) => {
          upstreamWs = ws;
          resolve();
        });
      });

      const client = await connectWs(proxyPort, "/devtools/browser/FAKE-UUID", {
        authorization: "Bearer valid-token",
      });
      expect(client.rejected).toBeUndefined();

      // Wait for upstream connection to be established
      await upstreamConnected;

      const upstreamClosed = new Promise((resolve) => {
        upstreamWs.on("close", resolve);
      });

      client.close();
      await upstreamClosed;
      expect(upstreamWs.readyState).toBe(WebSocket.CLOSED);
    }, 10000);

    it("closes downstream when upstream closes", async () => {
      mockBrowserless.wss.on("connection", (ws) => {
        setTimeout(() => ws.close(), 50);
      });

      const client = await connectWs(proxyPort, "/devtools/browser/FAKE-UUID", {
        authorization: "Bearer valid-token",
      });
      expect(client.rejected).toBeUndefined();

      const { code } = await waitForClose(client);
      expect(code).toBeDefined();
    }, 10000);
  });
});

// ---------------------------------------------------------------------------
// Unit tests for rewrite.js
// ---------------------------------------------------------------------------

describe("rewriteUrls", () => {
  let rewriteUrls;

  beforeAll(async () => {
    const mod = await import("../src/rewrite.js");
    rewriteUrls = mod.rewriteUrls;
  });

  it("rewrites single object", () => {
    const input = {
      webSocketDebuggerUrl: "ws://browserless:3000/devtools/browser/abc?token=xyz",
    };
    const result = rewriteUrls(input, "localhost:9223");
    expect(result.webSocketDebuggerUrl).toBe("ws://localhost:9223/devtools/browser/abc");
    expect(result.webSocketDebuggerUrl).not.toContain("token=");
  });

  it("rewrites array of objects", () => {
    const input = [
      { webSocketDebuggerUrl: "ws://host:3000/devtools/page/1?token=t", title: "Page 1" },
      { webSocketDebuggerUrl: "ws://host:3000/devtools/page/2?token=t", title: "Page 2" },
    ];
    const result = rewriteUrls(input, "proxy.example.com");
    expect(result).toHaveLength(2);
    expect(result[0].webSocketDebuggerUrl).toMatch(/^wss:\/\/proxy\.example\.com/);
    expect(result[1].webSocketDebuggerUrl).not.toContain("token=");
    expect(result[0].title).toBe("Page 1");
  });

  it("handles objects without webSocketDebuggerUrl", () => {
    const input = { Browser: "Chrome/123" };
    const result = rewriteUrls(input, "localhost:9223");
    expect(result).toEqual({ Browser: "Chrome/123" });
  });
});
