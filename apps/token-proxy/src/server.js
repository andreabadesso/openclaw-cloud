import http from "node:http";
import { config } from "./config.js";
import { authenticateToken } from "./auth.js";
import { checkRateLimit } from "./rate-limit.js";
import { checkLimits } from "./limits.js";
import { pushUsageEvent } from "./usage.js";
import { startUsageConsumer } from "./usage.js";
import { forwardRequest } from "./proxy.js";
import { handleInternal } from "./internal.js";
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
      res.end('{"status":"ok"}');
      return;
    }

    // Internal API routes
    if (req.url.startsWith("/internal/")) {
      await handleInternal(req, res, redis, pool);
      return;
    }

    // Proxy: POST /v1/*
    if (req.method === "POST" && req.url.startsWith("/v1/")) {
      await handleProxy(req, res);
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

async function handleProxy(req, res) {
  // 1. Extract Bearer token
  const authHeader = req.headers.authorization || "";
  if (!authHeader.startsWith("Bearer ")) {
    res.writeHead(401, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: { message: "Missing or invalid Authorization header", type: "auth_error" } }));
    return;
  }
  const token = authHeader.slice(7);

  // 2. Authenticate
  const customerId = await authenticateToken(token, redis, pool);
  if (customerId === null) {
    res.writeHead(401, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: { message: "Invalid proxy token", type: "auth_error" } }));
    return;
  }

  // 3. Rate limit
  if (!(await checkRateLimit(customerId, redis))) {
    res.writeHead(429, { "content-type": "application/json", "retry-after": "1" });
    res.end(JSON.stringify({ error: { message: "Rate limit exceeded (10 req/s)", type: "rate_limit_error" } }));
    return;
  }

  // 4. Check limits
  const limitResult = await checkLimits(customerId, redis, pool);
  if (!limitResult.allowed) {
    res.writeHead(429, { "content-type": "application/json" });
    res.end(JSON.stringify({
      error: {
        message: "Monthly token limit exceeded. Upgrade at app.openclaw.cloud/billing.",
        type: "monthly_limit_exceeded",
        used: limitResult.used,
        limit: limitResult.limit,
      },
    }));
    return;
  }

  // 5. Read body
  const body = await new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });

  // 6. Forward to upstream via pi-ai
  let usage;
  try {
    usage = await forwardRequest(body, res, limitResult);
  } catch (err) {
    console.error("Upstream error:", err);
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: { message: "Upstream API error", type: "upstream_error" } }));
    }
    return;
  }

  // 7. Record usage (fire-and-forget)
  const totalTokens = (usage.prompt_tokens || 0) + (usage.completion_tokens || 0);
  if (totalTokens > 0) {
    let model = usage.model || "unknown";
    try {
      const parsed = JSON.parse(body);
      if (!usage.model && parsed.model) model = parsed.model;
    } catch { /* ignore */ }

    pushUsageEvent(redis, {
      customer_id: customerId,
      box_id: null,
      model,
      prompt_tokens: usage.prompt_tokens,
      completion_tokens: usage.completion_tokens,
      request_id: usage.request_id || "",
    }).catch((err) => console.error("Failed to push usage event:", err));
  }
}

server.listen(config.port, () => {
  console.log(`Token proxy listening on :${config.port}`);
});
