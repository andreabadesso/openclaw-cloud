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
const redis = new Redis(config.redisUrl);
const pool = new Pool({ connectionString: config.databaseUrl, max: 10 });

// Start background usage consumer
startUsageConsumer(redis, pool);

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

async function handleJson(req, res) {
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
    // 1. Authenticate (Bearer token or Basic auth where username = token)
    const token = extractToken(req.headers.authorization || "");
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

    // 3. Build upstream WebSocket URL
    const upstreamUrl = buildUpstreamWsUrl(req.url);

    // 4. Connect to Browserless upstream
    const upstreamWs = new WebSocket(upstreamUrl);

    upstreamWs.on("error", (err) => {
      console.error("Upstream WS error:", err.message);
      socket.write("HTTP/1.1 502 Bad Gateway\r\n\r\n");
      socket.destroy();
    });

    upstreamWs.on("open", () => {
      // 5. Accept the downstream upgrade
      const wss = new WebSocketServer({ noServer: true });
      wss.handleUpgrade(req, socket, head, (downstreamWs) => {
        // 6. Register session
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

        // 7. Bidirectional piping
        downstreamWs.on("message", (data, isBinary) => {
          if (upstreamWs.readyState === WebSocket.OPEN) {
            upstreamWs.send(data, { binary: isBinary });
          }
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
