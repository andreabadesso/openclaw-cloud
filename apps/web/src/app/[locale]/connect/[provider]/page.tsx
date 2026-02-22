"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Nango from "@nangohq/frontend";

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
  const params = useParams();
  const searchParams = useSearchParams();
  const provider = params.provider as string;
  const token = searchParams.get("token");

  const [state, setState] = useState<State>("validating");
  const [error, setError] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState<string | null>(null);

  const startConnect = useCallback(async (custId: string) => {
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
      const { session_token } = await res.json();

      const nango = new Nango({
        host: "http://localhost:3003",
        connectSessionToken: session_token,
      });

      await nango.auth(provider);

      // After successful OAuth, confirm the connection
      try {
        await fetch(`/api/me/connections/${provider}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Customer-Id": custId },
        });
      } catch {
        // Connection may not have completed — that's OK
      }
      setState("success");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Connection failed";
      if (msg.includes("window_closed")) {
        setState("error");
        setError("Authorization window was closed. Please try again.");
      } else {
        setState("error");
        setError(msg);
      }
    }
  }, [provider]);

  useEffect(() => {
    if (!token) {
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

  const displayName = formatProvider(provider);

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
