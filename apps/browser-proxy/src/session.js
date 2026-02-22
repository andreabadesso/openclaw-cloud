import { randomUUID } from "node:crypto";
import { config } from "./config.js";

/**
 * In-memory session store.
 * Key: session UUID
 * Value: { customerId, upstreamWs, downstreamWs, startedAt, timer }
 */
const sessions = new Map();

/**
 * Count active sessions for a customer.
 * @param {string} customerId
 * @returns {number}
 */
export function countSessions(customerId) {
  let count = 0;
  for (const session of sessions.values()) {
    if (session.customerId === customerId) count++;
  }
  return count;
}

/**
 * Check whether a customer can open a new session.
 * @param {string} customerId
 * @returns {boolean}
 */
export function canOpenSession(customerId) {
  return countSessions(customerId) < config.maxConcurrentSessions;
}

/**
 * Create and register a new session.
 * @param {string} customerId
 * @param {import("ws").WebSocket} upstreamWs
 * @param {import("ws").WebSocket} downstreamWs
 * @param {() => void} onTimeout — called when the session exceeds max duration
 * @returns {string} session id
 */
export function createSession(customerId, upstreamWs, downstreamWs, onTimeout) {
  const id = randomUUID();
  const timer = setTimeout(() => {
    console.log(`Session ${id} exceeded max duration, closing`);
    onTimeout();
  }, config.maxSessionDurationMs);

  sessions.set(id, {
    customerId,
    upstreamWs,
    downstreamWs,
    startedAt: Date.now(),
    timer,
  });

  return id;
}

/**
 * Remove a session and clear its timer.
 * @param {string} id
 * @returns {{ customerId: string, durationMs: number } | null}
 */
export function removeSession(id) {
  const session = sessions.get(id);
  if (!session) return null;

  clearTimeout(session.timer);
  sessions.delete(id);

  return {
    customerId: session.customerId,
    durationMs: Date.now() - session.startedAt,
  };
}

/**
 * Close both sides of a session and remove it.
 * @param {string} id
 * @returns {{ customerId: string, durationMs: number } | null}
 */
export function closeSession(id) {
  const session = sessions.get(id);
  if (!session) return null;

  try { session.upstreamWs.close(1000); } catch { /* ignore */ }
  try { session.downstreamWs.close(1000); } catch { /* ignore */ }

  return removeSession(id);
}

/**
 * Get all active sessions (for internal API / health reporting).
 * @returns {Array<{ id: string, customerId: string, startedAt: number }>}
 */
export function listSessions() {
  const result = [];
  for (const [id, session] of sessions) {
    result.push({
      id,
      customerId: session.customerId,
      startedAt: session.startedAt,
    });
  }
  return result;
}
