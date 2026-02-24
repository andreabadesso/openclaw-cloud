import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";

type State = "validating" | "connecting" | "success" | "error";

function formatProvider(provider: string): string {
  const names: Record<string, string> = {
    github: "GitHub",
    gitlab: "GitLab",
    google: "Google",
    slack: "Slack",
    linear: "Linear",
    jira: "Jira",
    notion: "Notion",
  };
  return names[provider] ?? provider.charAt(0).toUpperCase() + provider.slice(1);
}

export default function ConnectProviderPage() {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [state, setState] = useState<State>("validating");
  const [error, setError] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);

  const startConnect = useCallback(async (custId: string) => {
    if (!provider) return;
    try {
      setState("connecting");
      const res = await fetch(`/api/me/connections/${provider}/authorize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Customer-Id": custId,
        },
      });
      if (!res.ok) throw new Error("Failed to start connection");
      const { connect_url } = await res.json();

      const popup = window.open(connect_url, "nango-connect", "width=600,height=700");

      const interval = setInterval(async () => {
        if (popup?.closed) {
          clearInterval(interval);
          try {
            const confirmRes = await fetch(`/api/me/connections/${provider}/confirm`, {
              method: "POST",
              headers: { "Content-Type": "application/json", "X-Customer-Id": custId },
            });
            if (confirmRes.ok) {
              setState("success");
            } else {
              const checkRes = await fetch(`/api/me/connections`, {
                headers: { "X-Customer-Id": custId },
              });
              const data = await checkRes.json();
              const connected = data.connections?.some(
                (c: { provider: string; status: string }) =>
                  c.provider === provider && c.status === "connected",
              );
              if (connected) {
                setState("success");
              } else {
                setState("error");
                setError("Connection was not completed. Please try again.");
              }
            }
          } catch {
            setState("error");
            setError("Could not verify connection status.");
          }
        }
      }, 500);
    } catch (e: unknown) {
      setState("error");
      setError(e instanceof Error ? e.message : "Connection failed");
    }
  }, [provider]);

  useEffect(() => {
    if (!token || !provider) {
      setState("error");
      setError("Missing token");
      return;
    }

    fetch(`/api/connect/${provider}/validate?token=${token}`)
      .then((r) => {
        if (!r.ok) throw new Error("Invalid or expired link");
        return r.json();
      })
      .then((data) => {
        setCustomerId(data.customer_id);
        startConnect(data.customer_id);
      })
      .catch((e) => {
        setState("error");
        setError(e.message);
      });
  }, [provider, token, startConnect]);

  const displayName = formatProvider(provider ?? "");

  if (state === "validating") {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
          <p className="mt-4 text-muted-foreground">Validating link...</p>
        </div>
      </div>
    );
  }

  if (state === "connecting") {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
          <p className="mt-4 text-muted-foreground">
            Connecting to {displayName}...
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Complete the authorization in the popup window.
          </p>
        </div>
      </div>
    );
  }

  if (state === "success") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <div className="rounded-lg border border-green-500/50 bg-green-500/10 p-6 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-500/20">
            <svg
              className="h-6 w-6 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4.5 12.75l6 6 9-13.5"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold">
            {displayName} Connected
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            You can close this page and go back to Telegram.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-16">
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6 text-center">
        <h2 className="font-semibold">Connection Failed</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {error ?? "An unknown error occurred."}
        </p>
        {customerId && (
          <button
            onClick={() => startConnect(customerId)}
            className="mt-4 inline-flex items-center rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}
