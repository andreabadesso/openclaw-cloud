import { config } from "./config.js";

const STREAM_KEY = "usage:events";
const CONSUMER_GROUP = "proxy-consumers";
const CONSUMER_NAME = "proxy-worker";

/**
 * Push a usage event to the Redis stream (fire-and-forget).
 * @param {import("ioredis").default} redis
 * @param {{customer_id: string, box_id?: string, model: string, prompt_tokens: number, completion_tokens: number, request_id: string}} event
 */
export async function pushUsageEvent(redis, event) {
  await redis.xadd(
    STREAM_KEY,
    "*",
    "customer_id", event.customer_id,
    "box_id", event.box_id || "",
    "model", event.model,
    "prompt_tokens", String(event.prompt_tokens),
    "completion_tokens", String(event.completion_tokens),
    "request_id", event.request_id,
    "timestamp", String(Date.now() / 1000),
  );
}

/**
 * Background loop: consume usage events from Redis stream, batch flush to Postgres.
 * @param {import("ioredis").default} redis
 * @param {import("pg").Pool} pg
 */
export async function startUsageConsumer(redis, pg) {
  // Create consumer group if needed
  try {
    await redis.xgroup("CREATE", STREAM_KEY, CONSUMER_GROUP, "0", "MKSTREAM");
  } catch {
    // Group already exists
  }

  let batch = [];
  let lastFlush = Date.now();

  while (true) {
    try {
      const messages = await redis.xreadgroup(
        "GROUP", CONSUMER_GROUP, CONSUMER_NAME,
        "COUNT", config.usageFlushBatchSize,
        "BLOCK", config.usageFlushIntervalMs,
        "STREAMS", STREAM_KEY, ">",
      );

      if (messages) {
        for (const [, entries] of messages) {
          for (const [msgId, fields] of entries) {
            // fields is flat array: [key, val, key, val, ...]
            const obj = { msg_id: msgId };
            for (let i = 0; i < fields.length; i += 2) {
              obj[fields[i]] = fields[i + 1];
            }
            batch.push(obj);
          }
        }
      }

      const elapsed = Date.now() - lastFlush;
      if (batch.length > 0 && (batch.length >= config.usageFlushBatchSize || elapsed >= config.usageFlushIntervalMs)) {
        await flushBatch(batch, redis, pg);
        const msgIds = batch.map((e) => e.msg_id);
        if (msgIds.length > 0) {
          await redis.xack(STREAM_KEY, CONSUMER_GROUP, ...msgIds);
        }
        batch = [];
        lastFlush = Date.now();
      }
    } catch (err) {
      console.error("Usage consumer error:", err);
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
}

async function flushBatch(batch, redis, pg) {
  if (batch.length === 0) return;

  const client = await pg.connect();
  try {
    await client.query("BEGIN");

    for (const event of batch) {
      if (!event.box_id) continue;
      await client.query(
        `INSERT INTO usage_events
         (customer_id, box_id, model, prompt_tokens, completion_tokens, request_id)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT DO NOTHING`,
        [
          event.customer_id,
          event.box_id,
          event.model,
          parseInt(event.prompt_tokens) || 0,
          parseInt(event.completion_tokens) || 0,
          event.request_id,
        ],
      );
    }

    // Aggregate by customer
    const customerTotals = {};
    for (const event of batch) {
      const cid = event.customer_id;
      const total = (parseInt(event.prompt_tokens) || 0) + (parseInt(event.completion_tokens) || 0);
      customerTotals[cid] = (customerTotals[cid] || 0) + total;
    }

    for (const [customerId, totalTokens] of Object.entries(customerTotals)) {
      await client.query(
        `UPDATE usage_monthly
         SET tokens_used = tokens_used + $1
         WHERE customer_id = $2
           AND period_start <= now()
           AND period_end > now()`,
        [totalTokens, customerId],
      );
    }

    await client.query("COMMIT");

    // Update Redis caches
    for (const [customerId, added] of Object.entries(customerTotals)) {
      const cacheKey = `limit:${customerId}`;
      const cached = await redis.get(cacheKey);
      if (cached !== null) {
        const data = JSON.parse(cached);
        data.used = data.used + added;
        // keepttl via TTL + set
        const ttl = await redis.ttl(cacheKey);
        if (ttl > 0) {
          await redis.set(cacheKey, JSON.stringify(data), "EX", ttl);
        }
      }
    }

    console.log(`Flushed ${batch.length} usage events for ${Object.keys(customerTotals).length} customers`);
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
