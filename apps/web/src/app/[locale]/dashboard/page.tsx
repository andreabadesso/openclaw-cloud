"use client";

import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { UsageGauge } from "@/components/usage-gauge";
import { api, type Box } from "@/lib/api";

export default function DashboardPage() {
  const [box, setBox] = useState<Box | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getBox("me")
      .then(setBox)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">Loading...</p>
      </div>
    );
  }

  if (error || !box) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6">
          <h2 className="font-semibold">Could not load your box</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {error ?? "No active instance found."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="mt-8 rounded-lg border bg-card p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Box Status</h2>
          <StatusBadge status={box.status} />
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Provisioned {new Date(box.created_at).toLocaleDateString()}
        </p>
      </div>

      <div className="mt-6 rounded-lg border bg-card p-6">
        <h2 className="mb-4 font-semibold">Token Usage</h2>
        <UsageGauge used={box.tokens_used} limit={box.tokens_limit} />
      </div>

      <div className="mt-6 rounded-lg border bg-card p-6">
        <h2 className="mb-4 font-semibold">Configuration</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Tier</dt>
            <dd className="mt-0.5 font-medium capitalize">{box.tier}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Model</dt>
            <dd className="mt-0.5 font-medium">{box.model}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Thinking Level</dt>
            <dd className="mt-0.5 font-medium capitalize">
              {box.thinking_level}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Language</dt>
            <dd className="mt-0.5 font-medium uppercase">{box.language}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted-foreground">Telegram Users</dt>
            <dd className="mt-0.5 font-medium">
              {box.telegram_user_ids.join(", ")}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-6">
        <a
          href="/billing"
          className="inline-flex items-center rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground hover:bg-secondary/80"
        >
          Manage Billing
        </a>
      </div>
    </div>
  );
}
