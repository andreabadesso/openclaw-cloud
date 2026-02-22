import { config } from "./config.js";

const STREAM_KEY = "browser-usage:events";
const CONSUMER_GROUP = "browser-consumers";
const CONSUMER_NAME = "browser-worker";

/**
 * Push a browser session event to the Redis stream.
 * @param {import("ioredis").default} redis
 * @param {{customer_id: string, box_id?: string, session_id: string, event_type: "session_start"|"session_end", duration_ms?: number}} event
 */
export async function pushSessionEvent(redis, event) {
  await redis.xadd(
    STREAM_KEY,
    "*",
    "customer_id", event.customer_id,
    "box_id", event.box_id || "",
    "session_id", event.session_id,
    "event_type", event.event_type,
    "duration_ms", String(event.duration_ms || 0),
    "timestamp", String(Date.now() / 1000),
  );
}

/**
 * Background loop: consume browser session events from Redis stream and persist to Postgres.
 *
 * Postgres table (migration managed separately):
 *   CREATE TABLE browser_sessions (
 *       id UUID PRIMARY KEY,
 *       customer_id UUID NOT NULL,
 *       box_id TEXT,
 *       started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 *       ended_at TIMESTAMPTZ,
 *       duration_ms INTEGER
 *   );
 *
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
      console.error("Browser usage consumer error:", err);
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
}

async function flushBatch(batch, _redis, pg) {
  if (batch.length === 0) return;

  const client = await pg.connect();
  try {
    await client.query("BEGIN");

    for (const event of batch) {
      if (event.event_type === "session_start") {
        await client.query(
          `INSERT INTO browser_sessions (id, customer_id, box_id, started_at)
           VALUES ($1, $2, $3, to_timestamp($4))
           ON CONFLICT (id) DO NOTHING`,
          [
            event.session_id,
            event.customer_id,
            event.box_id || null,
            parseFloat(event.timestamp),
          ],
        );
      } else if (event.event_type === "session_end") {
        await client.query(
          `UPDATE browser_sessions
           SET ended_at = to_timestamp($1), duration_ms = $2
           WHERE id = $3`,
          [
            parseFloat(event.timestamp),
            parseInt(event.duration_ms) || 0,
            event.session_id,
          ],
        );
      }
    }

    await client.query("COMMIT");

    const starts = batch.filter((e) => e.event_type === "session_start").length;
    const ends = batch.filter((e) => e.event_type === "session_end").length;
    console.log(`Flushed ${batch.length} browser session events (${starts} starts, ${ends} ends)`);
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
