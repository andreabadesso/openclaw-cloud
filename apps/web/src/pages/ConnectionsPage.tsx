import { useEffect, useState, useCallback } from "react";
import Nango from "@nangohq/frontend";
import { api, type Connection, type Box, type BundleListItem } from "@/lib/api";

const NANGO_URL = import.meta.env.VITE_NANGO_URL || "http://localhost:3003";

const PROVIDERS = [
  { id: "github", name: "GitHub", description: "Repositories, issues, and pull requests" },
  { id: "google", name: "Google", description: "Drive, Sheets, Calendar, and Gmail" },
  { id: "slack", name: "Slack", description: "Channels, messages, and notifications" },
  { id: "linear", name: "Linear", description: "Issues, projects, and cycles" },
  { id: "notion", name: "Notion", description: "Pages, databases, and wikis" },
  { id: "jira", name: "Jira", description: "Issues, boards, and sprints" },
];

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  github: (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
    </svg>
  ),
  google: (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  ),
  slack: (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor">
      <path d="M5.042 15.165a2.528 2.528 0 01-2.52 2.523A2.528 2.528 0 010 15.165a2.527 2.527 0 012.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 012.521-2.52 2.527 2.527 0 012.521 2.52v6.313A2.528 2.528 0 018.834 24a2.528 2.528 0 01-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 01-2.521-2.52A2.528 2.528 0 018.834 0a2.528 2.528 0 012.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 012.521 2.521 2.528 2.528 0 01-2.521 2.521H2.522A2.528 2.528 0 010 8.834a2.528 2.528 0 012.522-2.521h6.312zM18.956 8.834a2.528 2.528 0 012.522-2.521A2.528 2.528 0 0124 8.834a2.528 2.528 0 01-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 01-2.523 2.521 2.527 2.527 0 01-2.52-2.521V2.522A2.527 2.527 0 0115.163 0a2.528 2.528 0 012.523 2.522v6.312zM15.163 18.956a2.528 2.528 0 012.523 2.522A2.528 2.528 0 0115.163 24a2.527 2.527 0 01-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 01-2.52-2.523 2.527 2.527 0 012.52-2.52h6.315A2.528 2.528 0 0124 15.163a2.528 2.528 0 01-2.522 2.523h-6.315z" />
    </svg>
  ),
  linear: (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor">
      <path d="M2.262 15.702a.506.506 0 01-.128-.542 10.018 10.018 0 012.414-3.86l7.152 7.152a10.02 10.02 0 01-3.86 2.414.506.506 0 01-.542-.128l-5.036-5.036zM1.02 12.078a.504.504 0 01-.019-.618A10.016 10.016 0 0111.98 5.03a.504.504 0 01.388.872L2.37 15.9a.504.504 0 01-.778-.056 10.064 10.064 0 01-.572-3.766zM12.98 5.03c3.238.482 5.831 2.904 6.6 6.07a.504.504 0 01-.133.48l-6.947 6.947a.504.504 0 01-.48.133 8.16 8.16 0 01-6.07-6.6.504.504 0 01.143-.435l6.452-6.452a.504.504 0 01.435-.143zM22 12c0 .396-.023.787-.068 1.172a.504.504 0 01-.848.296l-6.552-6.552a.504.504 0 01.296-.848A10.023 10.023 0 0122 12z" />
    </svg>
  ),
  notion: (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor">
      <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L18.38 2.168c-.42-.326-.98-.7-2.055-.606L3.293 2.63c-.466.046-.56.28-.373.466l1.54 1.112zm.793 3.172v13.857c0 .746.373 1.026 1.213.98l14.523-.84c.84-.046.933-.56.933-1.166V6.354c0-.606-.233-.886-.746-.84l-15.177.886c-.56.046-.746.28-.746.98zM18.52 7.5c.093.42 0 .84-.42.886l-.7.14v10.264c-.606.326-1.166.514-1.633.514-.746 0-.933-.234-1.493-.933l-4.572-7.186v6.953l1.446.327s0 .84-1.166.84l-3.22.186c-.092-.186 0-.653.327-.746l.84-.233V9.854L6.379 9.76c-.093-.42.14-1.026.793-1.073l3.453-.233 4.759 7.28V9.434l-1.213-.14c-.093-.513.28-.886.746-.932l3.453-.233.14.886.006-.014z" />
    </svg>
  ),
  jira: (
    <svg viewBox="0 0 24 24" className="h-6 w-6" fill="currentColor">
      <path d="M11.571 11.513H0a5.218 5.218 0 005.232 5.215h2.13v2.057A5.215 5.215 0 0012.575 24V12.518a1.005 1.005 0 00-1.005-1.005zm5.723-5.756H5.736a5.215 5.215 0 005.215 5.214h2.129v2.058a5.218 5.218 0 005.215 5.214V6.758a1.001 1.001 0 00-1.001-1.001zM23 .006H11.429a5.214 5.214 0 005.214 5.214h2.129v2.058A5.218 5.218 0 0023.986 12.5V1.005A1.001 1.001 0 0022.985.006z" fill="#2684FF" />
    </svg>
  ),
};

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [requiredProviders, setRequiredProviders] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchConnections = useCallback(() => {
    api
      .getConnections()
      .then(setConnections)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchConnections();
    Promise.all([
      api.getBox("me").catch(() => null),
      api.getBundles().catch(() => []),
    ]).then(([box, bundles]) => {
      if (box?.bundle_id) {
        const bundle = bundles.find((b: BundleListItem) => b.id === box.bundle_id);
        if (bundle) {
          setRequiredProviders(
            new Set(bundle.providers.filter((p) => p.required).map((p) => p.provider))
          );
        }
      }
    });
  }, [fetchConnections]);

  function getConnection(providerId: string): Connection | undefined {
    return connections.find((c) => c.provider === providerId);
  }

  async function handleConnect(providerId: string) {
    setActionLoading(providerId);
    try {
      const session = await api.authorizeConnection(providerId);

      const nango = new Nango({
        host: NANGO_URL,
        connectSessionToken: session.session_token,
      });

      await nango.auth(providerId);

      try {
        await api.confirmConnection(providerId);
      } catch {
        // Connection may not have completed
      }
      fetchConnections();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to connect";
      if (!msg.includes("window_closed")) {
        setError(msg);
      }
    } finally {
      setActionLoading(null);
    }
  }

  async function handleDisconnect(connectionId: string) {
    setActionLoading(connectionId);
    try {
      await api.deleteConnection(connectionId);
      fetchConnections();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to disconnect");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReconnect(connectionId: string, providerId: string) {
    setActionLoading(connectionId);
    try {
      const session = await api.reconnectConnection(connectionId);

      const nango = new Nango({
        host: NANGO_URL,
        connectSessionToken: session.session_token,
      });

      await nango.auth(providerId);

      try {
        await api.confirmConnection(providerId);
      } catch {
        // Connection may not have completed
      }
      fetchConnections();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to reconnect";
      if (!msg.includes("window_closed")) {
        setError(msg);
      }
    } finally {
      setActionLoading(null);
    }
  }

  if (loading) {
    return (
      <div>
        <div className="skeleton mb-2 h-8 w-40" />
        <div className="skeleton mb-8 h-4 w-72" />
        <div className="grid gap-4 sm:grid-cols-2">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="skeleton h-36 rounded-xl"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white/90">Connections</h1>
      <p className="mt-1 text-sm text-white/40">
        Connect your tools to enable OpenClaw to work with your services.
      </p>

      {error && (
        <div className="animate-fade-up mt-4 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <p className="text-sm text-red-400">{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-1 text-xs text-white/40 hover:text-white/60"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {PROVIDERS.map((provider, i) => {
          const conn = getConnection(provider.id);
          const isConnected = conn?.status === "connected";
          const isError = conn?.status === "error";
          const isLoading =
            actionLoading === provider.id || actionLoading === conn?.id;

          return (
            <div
              key={provider.id}
              className={`animate-fade-up rounded-xl border border-white/[0.06] bg-white/[0.02] p-5 card-glow delay-${(i + 1) * 100}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/[0.04] text-white/60">
                    {PROVIDER_ICONS[provider.id] ?? (
                      <span className="text-sm font-bold">
                        {provider.name[0]}
                      </span>
                    )}
                  </div>
                  <div>
                    <h3 className="font-semibold text-white/90">
                      {provider.name}
                    </h3>
                    <p className="text-xs text-white/40">
                      {provider.description}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {requiredProviders.has(provider.id) && (
                    <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-medium text-amber-400">
                      Required
                    </span>
                  )}
                  {isConnected && (
                    <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                      <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                      Connected
                    </span>
                  )}
                  {isError && (
                    <span className="flex items-center gap-1.5 text-xs text-red-400">
                      <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                      Error
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-4">
                {isConnected && conn && (
                  <button
                    onClick={() => handleDisconnect(conn.id)}
                    disabled={isLoading}
                    className="rounded-lg border border-white/[0.08] px-3 py-1.5 text-sm text-white/50 transition-all hover:border-white/[0.15] hover:text-white/70 disabled:opacity-50"
                  >
                    {isLoading ? "Disconnecting..." : "Disconnect"}
                  </button>
                )}
                {isError && conn && (
                  <button
                    onClick={() => handleReconnect(conn.id, provider.id)}
                    disabled={isLoading}
                    className="rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-medium text-black transition-all hover:bg-emerald-400 disabled:opacity-50"
                  >
                    {isLoading ? "Reconnecting..." : "Reconnect"}
                  </button>
                )}
                {!conn && (
                  <button
                    onClick={() => handleConnect(provider.id)}
                    disabled={isLoading}
                    className="rounded-lg bg-emerald-500 px-3 py-1.5 text-sm font-medium text-black transition-all hover:bg-emerald-400 disabled:opacity-50"
                  >
                    {isLoading ? "Connecting..." : "Connect"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
