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
  if (v >= 1024 * 1024 * 1024)
    return `${(v / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
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
      <div>
        <div className="skeleton mb-8 h-8 w-32" />
        <div className="space-y-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="skeleton h-48 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
        <h2 className="font-semibold text-red-400">
          Could not load analytics
        </h2>
        <p className="mt-1 text-sm text-white/50">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const limits = TIER_LIMITS[data.tier] ?? TIER_LIMITS.starter;
  const cpuSeries = data.pod_metrics_series.map((p) => ({
    value: p.cpu_millicores,
    ts: p.ts,
  }));
  const memSeries = data.pod_metrics_series.map((p) => ({
    value: p.memory_bytes,
    ts: p.ts,
  }));

  return (
    <div>
      <h1 className="text-2xl font-bold text-white/90">Analytics</h1>
      <p className="mt-1 text-sm text-white/40">
        Usage metrics for the last 24 hours.
      </p>

      <div className="mt-8 space-y-6">
        {/* Token usage */}
        <div className="animate-fade-up rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">
            Token Usage
          </h2>
          <UsageGauge
            used={data.token_usage.tokens_used}
            limit={data.token_usage.tokens_limit}
          />
        </div>

        {/* Browser sessions */}
        <div className="animate-fade-up delay-100 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="text-sm font-medium text-white/50">
            Browser Sessions
          </h2>
          <p className="mt-0.5 text-xs text-white/30">Last 24 hours</p>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <p className="text-3xl font-bold text-white/90">
                {data.browser_sessions.session_count}
              </p>
              <p className="text-xs text-white/40">Sessions</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-white/90">
                {formatDuration(data.browser_sessions.total_duration_ms)}
              </p>
              <p className="text-xs text-white/40">Total Duration</p>
            </div>
          </div>
        </div>

        {/* CPU chart */}
        <div className="animate-fade-up delay-200">
          <MetricsChart
            data={cpuSeries}
            label="CPU Usage (24h)"
            color="#3b82f6"
            limitValue={limits.cpu}
            maxValue={limits.cpu * 1.2}
            formatValue={formatCpu}
          />
        </div>

        {/* Memory chart */}
        <div className="animate-fade-up delay-300">
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
    </div>
  );
}
