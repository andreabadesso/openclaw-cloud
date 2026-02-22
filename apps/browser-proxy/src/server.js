import http from "node:http";
import { config } from "./config.js";
import { authenticateToken } from "./auth.js";
import { rewriteUrls } from "./rewrite.js";
import {
  canOpenSession,
  createSession,
  closeSession,
  removeSession,
  listSessions,
} from "./session.js";
import { pushSessionEvent, startUsageConsumer } from "./usage.js";
import { handleInternal } from "./internal.js";
import { WebSocket, WebSocketServer } from "ws";
import Redis from "ioredis";
import pg from "pg";

const { Pool } = pg;

// Initialize connections
// IMPORTANT: separate Redis clients for blocking vs non-blocking operations.
// The usage consumer uses XREADGROUP with BLOCK which holds the connection for
// up to 5s at a time. If we share one client, ALL Redis ops (auth cache lookups,
// session events) are blocked waiting for the XREADGROUP to release.
const redis = new Redis(config.redisUrl);
const redisBlocking = new Redis(config.redisUrl);
const pool = new Pool({ connectionString: config.databaseUrl, max: 10 });

// Start background usage consumer (uses its own blocking Redis client)
startUsageConsumer(redisBlocking, pool);

const server = http.createServer(async (req, res) => {
  try {
    // Health check
    if (req.method === "GET" && req.url === "/health") {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ status: "ok", sessions: listSessions().length }));
      return;
    }

    // Internal API routes
    if (req.url.startsWith("/internal/")) {
      await handleInternal(req, res, redis, pool);
      return;
    }

    // /json/* and /devtools/* endpoints — forward to Browserless
    if (req.url.startsWith("/json") || req.url.startsWith("/devtools")) {
      await handleJson(req, res);
      return;
    }

    res.writeHead(404, { "content-type": "application/json" });
    res.end('{"error":{"message":"Not found","type":"not_found"}}');
  } catch (err) {
    console.error("Request error:", err);
    if (!res.headersSent) {
      res.writeHead(500, { "content-type": "application/json" });
      res.end('{"error":{"message":"Internal server error","type":"server_error"}}');
    }
  }
});

// ─── /json/* handler ────────────────────────────────────────────────

// Cache /json/version responses for 30s to avoid 800ms+ Browserless round-trips
// on every CDP health check from the gateway.
let versionCache = { data: null, host: null, expiry: 0 };

async function handleJson(req, res) {
  // Serve /json/version from cache if fresh
  if (req.url.startsWith("/json/version")) {
    // Pre-warm auth cache: if ?token= is present, AWAIT authenticateToken so the
    // subsequent WS health check (which also carries ?token=) hits the Redis cache
    // instead of running slow bcrypt comparisons (~700ms each on limited CPU).
    try {
      const url = new URL(req.url, `http://${req.headers.host}`);
      const token = url.searchParams.get("token");
      if (token) {
        await authenticateToken(token, redis, pool);
      }
    } catch { /* ignore */ }

    const proxyHost = req.headers.host || `localhost:${config.port}`;
    if (versionCache.data && versionCache.host === proxyHost && Date.now() < versionCache.expiry) {
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(versionCache.data));
      return;
    }
  }

  const upstreamUrl = buildUpstreamHttpUrl(req.url);

  let upstream;
  try {
    upstream = await fetch(upstreamUrl, { method: req.method });
  } catch (err) {
    console.error("Browserless /json fetch error:", err);
    res.writeHead(502, { "content-type": "application/json" });
    res.end('{"error":{"message":"Failed to reach Browserless","type":"upstream_error"}}');
    return;
  }

  const contentType = upstream.headers.get("content-type") || "application/json";
  const body = await upstream.text();

  // Try to parse and rewrite URLs
  try {
    const data = JSON.parse(body);
    const proxyHost = req.headers.host || `localhost:${config.port}`;
    const rewritten = rewriteUrls(data, proxyHost);

    // Cache /json/version
    if (req.url.startsWith("/json/version")) {
      versionCache = { data: rewritten, host: proxyHost, expiry: Date.now() + 30_000 };
    }

    res.writeHead(upstream.status, { "content-type": contentType });
    res.end(JSON.stringify(rewritten));
  } catch {
    // If not JSON, pass through as-is
    res.writeHead(upstream.status, { "content-type": contentType });
    res.end(body);
  }
}

// ─── WebSocket upgrade handler ──────────────────────────────────────

server.on("upgrade", async (req, socket, head) => {
  try {
    // 1. Authenticate (Bearer/Basic header, or ?token= query param)
    let token = extractToken(req.headers.authorization || "");
    if (!token) {
      // Fallback: extract token from query string (?token=xxx)
      try {
        const url = new URL(req.url, `http://${req.headers.host}`);
        token = url.searchParams.get("token") || null;
      } catch { /* ignore */ }
    }
    if (!token) {
      socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
      socket.destroy();
      return;
    }

    const auth = await authenticateToken(token, redis, pool);
    if (auth === null) {
      socket.write("HTTP/1.1 401 Unauthorized\r\n\r\n");
      socket.destroy();
      return;
    }
    const customerId = auth.customer_id;

    // 2. Check session limit
    if (!canOpenSession(customerId)) {
      socket.write(
        "HTTP/1.1 429 Too Many Requests\r\n" +
        "Content-Type: application/json\r\n\r\n" +
        JSON.stringify({
          error: {
            message: `Max concurrent sessions (${config.maxConcurrentSessions}) reached`,
            type: "session_limit_error",
          },
        }),
      );
      socket.destroy();
      return;
    }

    // 3. Accept the downstream WebSocket immediately so health checks
    //    (gateway's canOpenWebSocket) get "open" fast without waiting
    //    for the ~5s Browserless upstream connection.
    const wss = new WebSocketServer({ noServer: true });
    wss.handleUpgrade(req, socket, head, (downstreamWs) => {
      // 4. Build upstream WebSocket URL and connect lazily
      const upstreamUrl = buildUpstreamWsUrl(req.url);
      const upstreamWs = new WebSocket(upstreamUrl);

      // Buffer downstream messages until upstream is ready
      const pendingMessages = [];
      let upstreamReady = false;

      // 5. Register session
      let sessionId;
      let cleaned = false;
      const cleanup = () => {
        if (cleaned) return;
        cleaned = true;
        const info = removeSession(sessionId);
        if (info) {
          console.log(
            `Session ${sessionId} closed (customer=${info.customerId}, duration=${info.durationMs}ms)`,
          );
          pushSessionEvent(redis, {
            customer_id: info.customerId,
            session_id: sessionId,
            event_type: "session_end",
            duration_ms: info.durationMs,
          }).catch((err) => console.error("Failed to push session_end event:", err));
        }
      };

      sessionId = createSession(customerId, upstreamWs, downstreamWs, () => {
        // Max duration timeout
        try { upstreamWs.close(1000, "Session timeout"); } catch { /* ignore */ }
        try { downstreamWs.close(1000, "Session timeout"); } catch { /* ignore */ }
      });

      console.log(`Session ${sessionId} opened (customer=${customerId})`);

      pushSessionEvent(redis, {
        customer_id: customerId,
        session_id: sessionId,
        event_type: "session_start",
      }).catch((err) => console.error("Failed to push session_start event:", err));

      // 6. Downstream → upstream (buffer until upstream ready)
      downstreamWs.on("message", (data, isBinary) => {
        if (upstreamReady && upstreamWs.readyState === WebSocket.OPEN) {
          upstreamWs.send(data, { binary: isBinary });
        } else {
          pendingMessages.push({ data, isBinary });
        }
      });

      // 7. When upstream opens, flush buffer and start piping
      upstreamWs.on("open", () => {
        upstreamReady = true;
        for (const msg of pendingMessages) {
          if (upstreamWs.readyState === WebSocket.OPEN) {
            upstreamWs.send(msg.data, { binary: msg.isBinary });
          }
        }
        pendingMessages.length = 0;
      });

      upstreamWs.on("message", (data, isBinary) => {
        if (downstreamWs.readyState === WebSocket.OPEN) {
          downstreamWs.send(data, { binary: isBinary });
        }
      });

      // 8. Cleanup on close/error
      downstreamWs.on("close", () => {
        try { upstreamWs.close(1000); } catch { /* ignore */ }
        cleanup();
      });
      downstreamWs.on("error", (err) => {
        console.error(`Downstream WS error (session=${sessionId}):`, err.message);
        try { upstreamWs.close(1000); } catch { /* ignore */ }
        cleanup();
      });

      upstreamWs.on("close", () => {
        try { downstreamWs.close(1000); } catch { /* ignore */ }
        cleanup();
      });

      upstreamWs.on("error", (err) => {
        console.error(`Upstream WS error (session=${sessionId}):`, err.message);
        try { downstreamWs.close(1000); } catch { /* ignore */ }
        cleanup();
      });
    });
  } catch (err) {
    console.error("WebSocket upgrade error:", err);
    socket.write("HTTP/1.1 500 Internal Server Error\r\n\r\n");
    socket.destroy();
  }
});

// ─── Auth helpers ───────────────────────────────────────────────────

/**
 * Extract token from Authorization header.
 * Supports "Bearer <token>" and "Basic <base64>" (username = token, password ignored).
 */
function extractToken(authHeader) {
  if (authHeader.startsWith("Bearer ")) {
    return authHeader.slice(7);
  }
  if (authHeader.startsWith("Basic ")) {
    try {
      const decoded = Buffer.from(authHeader.slice(6), "base64").toString();
      const colon = decoded.indexOf(":");
      return colon >= 0 ? decoded.slice(0, colon) : decoded;
    } catch {
      return null;
    }
  }
  return null;
}

// ─── URL helpers ────────────────────────────────────────────────────

/**
 * Build the upstream HTTP URL for /json/* requests.
 * Appends the path to the Browserless base URL, preserving the token query param.
 */
function buildUpstreamHttpUrl(path) {
  const base = new URL(config.browserlessUrl);
  const upstream = new URL(path, base);
  // Preserve the token from BROWSERLESS_URL
  for (const [key, value] of base.searchParams) {
    upstream.searchParams.set(key, value);
  }
  return upstream.toString();
}

/**
 * Build the upstream WebSocket URL.
 * Converts http(s) to ws(s), appends path, preserves token query param.
 */
function buildUpstreamWsUrl(path) {
  const base = new URL(config.browserlessUrl);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  const upstream = new URL(path, base);
  // Preserve the token from BROWSERLESS_URL
  for (const [key, value] of base.searchParams) {
    upstream.searchParams.set(key, value);
  }
  return upstream.toString();
}

// ─── Start ──────────────────────────────────────────────────────────

server.listen(config.port, () => {
  console.log(`Browser proxy listening on :${config.port}`);
});

export { server };
