"use client";

import { useEffect, useState } from "react";
import { MetricsChart } from "@/components/metrics-chart";
import { UsageGauge } from "@/components/usage-gauge";
import { api, type AnalyticsData } from "@/lib/api";

const TIER_LIMITS: Record<string, { cpu: number; memory: number }> = {
  starter: { cpu: 1000, memory: 1024 * 1024 * 1024 },
  pro: { cpu: 2000, memory: 1024 * 1024 * 1024 },
  team: { cpu: 4000, memory: 2 * 1024 * 1024 * 1024 },
};

function formatCpu(v: number) {
  return v >= 1000 ? `${(v / 1000).toFixed(1)} cores` : `${v}m`;
}

function formatMemory(v: number) {
  if (v >= 1024 * 1024 * 1024) return `${(v / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
  return `${(v / (1024 * 1024)).toFixed(0)} MiB`;
}

function formatDuration(ms: number) {
  if (ms < 60_000) return `${(ms / 1000).toFixed(0)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getAnalytics(24)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">Loading analytics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-6">
          <h2 className="font-semibold">Could not load analytics</h2>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const limits = TIER_LIMITS[data.tier] ?? TIER_LIMITS.starter;
  const cpuSeries = data.pod_metrics_series.map((p) => ({ value: p.cpu_millicores, ts: p.ts }));
  const memSeries = data.pod_metrics_series.map((p) => ({ value: p.memory_bytes, ts: p.ts }));

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Analytics</h1>
        <a
          href="/dashboard"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Back to Dashboard
        </a>
      </div>

      <div className="mt-8 rounded-lg border bg-card p-6">
        <h2 className="mb-4 font-semibold">Token Usage</h2>
        <UsageGauge
          used={data.token_usage.tokens_used}
          limit={data.token_usage.tokens_limit}
        />
      </div>

      <div className="mt-6 rounded-lg border bg-card p-6">
        <h2 className="font-semibold">Browser Sessions</h2>
        <p className="mt-1 text-sm text-muted-foreground">Last 24 hours</p>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div>
            <p className="text-3xl font-bold">{data.browser_sessions.session_count}</p>
            <p className="text-xs text-muted-foreground">Sessions</p>
          </div>
          <div>
            <p className="text-3xl font-bold">
              {formatDuration(data.browser_sessions.total_duration_ms)}
            </p>
            <p className="text-xs text-muted-foreground">Total Duration</p>
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-6">
        <MetricsChart
          data={cpuSeries}
          label="CPU Usage (24h)"
          color="#3b82f6"
          limitValue={limits.cpu}
          maxValue={limits.cpu * 1.2}
          formatValue={formatCpu}
        />
        <MetricsChart
          data={memSeries}
          label="Memory Usage (24h)"
          color="#8b5cf6"
          limitValue={limits.memory}
          maxValue={limits.memory * 1.2}
          formatValue={formatMemory}
        />
      </div>
    </div>
  );
}
