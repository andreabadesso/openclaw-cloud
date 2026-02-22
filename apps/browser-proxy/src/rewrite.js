/**
 * Rewrite webSocketDebuggerUrl in /json/* responses from Browserless
 * to point through the proxy instead of directly to Browserless.
 *
 * @param {object|object[]} data — parsed JSON from Browserless /json/* endpoint
 * @param {string} proxyHost — the proxy's external host (from incoming Host header)
 * @returns {object|object[]} — data with rewritten URLs
 */
export function rewriteUrls(data, proxyHost) {
  // Always use plain ws:// — the proxy itself does not terminate TLS.
  // A TLS-terminating reverse proxy in front would handle wss:// externally.
  const protocol = "ws";

  if (Array.isArray(data)) {
    return data.map((entry) => rewriteEntry(entry, proxyHost, protocol));
  }
  return rewriteEntry(data, proxyHost, protocol);
}

function rewriteEntry(entry, proxyHost, protocol) {
  if (!entry || typeof entry !== "object") return entry;

  const result = { ...entry };

  if (typeof result.webSocketDebuggerUrl === "string") {
    result.webSocketDebuggerUrl = rewriteWsUrl(
      result.webSocketDebuggerUrl,
      proxyHost,
      protocol,
    );
  }

  return result;
}

/**
 * Replace host/port in a ws:// or wss:// URL with proxyHost and strip ?token= params.
 *
 * Example:
 *   "ws://browserless:3000/devtools/browser/abc?token=xyz"
 *   → "wss://proxy.example.com/devtools/browser/abc"
 */
function rewriteWsUrl(url, proxyHost, protocol) {
  try {
    const parsed = new URL(url);
    parsed.protocol = protocol + ":";
    parsed.host = proxyHost;
    parsed.searchParams.delete("token");
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return url;
  }
}
