"use client";

import { useEffect, useState, useCallback } from "react";
import Nango from "@nangohq/frontend";
import { api, type Connection } from "@/lib/api";

const PROVIDERS = [
  { id: "github", name: "GitHub", description: "Repositories, issues, and pull requests" },
  { id: "google", name: "Google", description: "Drive, Sheets, Calendar, and Gmail" },
  { id: "slack", name: "Slack", description: "Channels, messages, and notifications" },
  { id: "linear", name: "Linear", description: "Issues, projects, and cycles" },
  { id: "notion", name: "Notion", description: "Pages, databases, and wikis" },
  { id: "jira", name: "Jira", description: "Issues, boards, and sprints" },
];

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[]>([]);
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
  }, [fetchConnections]);

  function getConnection(providerId: string): Connection | undefined {
    return connections.find((c) => c.provider === providerId);
  }

  async function handleConnect(providerId: string) {
    setActionLoading(providerId);
    try {
      const session = await api.authorizeConnection(providerId);

      const nango = new Nango({
        host: "http://localhost:3003",
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
        host: "http://localhost:3003",
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
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold">Connections</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Connect your tools to enable OpenClaw to work with your services.
      </p>

      {error && (
        <div className="mt-4 rounded-lg border border-destructive/50 bg-destructive/10 p-4">
          <p className="text-sm">{error}</p>
          <button
            onClick={() => setError(null)}
            className="mt-1 text-xs text-muted-foreground hover:text-foreground"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {PROVIDERS.map((provider) => {
          const conn = getConnection(provider.id);
          const isConnected = conn?.status === "connected";
          const isError = conn?.status === "error";
          const isLoading =
            actionLoading === provider.id || actionLoading === conn?.id;

          return (
            <div
              key={provider.id}
              className="rounded-lg border bg-card p-5"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{provider.name}</h3>
                {isConnected && (
                  <span className="flex items-center gap-1.5 text-xs text-emerald-500">
                    <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                    Connected
                  </span>
                )}
                {isError && (
                  <span className="flex items-center gap-1.5 text-xs text-red-500">
                    <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
                    Error
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {provider.description}
              </p>
              <div className="mt-4">
                {isConnected && conn && (
                  <button
                    onClick={() => handleDisconnect(conn.id)}
                    disabled={isLoading}
                    className="rounded-md border px-3 py-1.5 text-sm text-muted-foreground hover:bg-secondary disabled:opacity-50"
                  >
                    {isLoading ? "Disconnecting..." : "Disconnect"}
                  </button>
                )}
                {isError && conn && (
                  <button
                    onClick={() => handleReconnect(conn.id, provider.id)}
                    disabled={isLoading}
                    className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                  >
                    {isLoading ? "Reconnecting..." : "Reconnect"}
                  </button>
                )}
                {!conn && (
                  <button
                    onClick={() => handleConnect(provider.id)}
                    disabled={isLoading}
                    className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
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
