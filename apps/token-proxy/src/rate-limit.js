import { config } from "./config.js";

const LUA_SCRIPT = `
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])

local bucket = redis.call('HMGET', key, 'tokens', 'last')
local tokens = tonumber(bucket[1])
local last = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last = now
end

local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens < 1 then
    return 0
end

tokens = tokens - 1
redis.call('HMSET', key, 'tokens', tokens, 'last', now)
redis.call('EXPIRE', key, 10)
return 1
`;

/**
 * Token bucket rate limiter. Returns true if allowed.
 * @param {string} customerId
 * @param {import("ioredis").default} redis
 * @returns {Promise<boolean>}
 */
export async function checkRateLimit(customerId, redis) {
  const key = `ratelimit:${customerId}`;
  const now = Date.now() / 1000;
  const result = await redis.eval(
    LUA_SCRIPT,
    1,
    key,
    config.rateLimitRps,
    now,
    config.rateLimitRps,
  );
  return result === 1;
}
