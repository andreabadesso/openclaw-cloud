"use client";

import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/status-badge";
import { UsageGauge } from "@/components/usage-gauge";
import { api, type Box, type Connection, type AnalyticsData } from "@/lib/api";
import { Link } from "@/i18n/navigation";
import {
  Globe,
  Plug,
  ArrowRight,
  Cpu,
  Brain,
  Languages,
  Target,
} from "lucide-react";

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return "N/A";
  const diff = Date.now() - new Date(dateStr).getTime();
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  if (days > 0) return `${days}d ${hours}h`;
  const mins = Math.floor((diff % 3600000) / 60000);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 ${className}`}
    >
      <div className="skeleton mb-4 h-4 w-24" />
      <div className="skeleton h-8 w-32" />
    </div>
  );
}

export default function DashboardPage() {
  const [box, setBox] = useState<Box | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.getBox("me"),
      api.getConnections().catch(() => [] as Connection[]),
      api.getAnalytics(24).catch(() => null),
    ])
      .then(([b, c, a]) => {
        setBox(b);
        setConnections(c);
        setAnalytics(a);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <div className="skeleton mb-8 h-8 w-40" />
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error || !box) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
        <h2 className="font-semibold text-red-400">Could not load your box</h2>
        <p className="mt-1 text-sm text-white/50">
          {error ?? "No active instance found."}
        </p>
      </div>
    );
  }

  const statusColor =
    box.status === "active"
      ? "bg-emerald-500"
      : box.status === "suspended"
        ? "bg-amber-500"
        : "bg-red-500";

  const connectedCount = connections.filter(
    (c) => c.status === "connected",
  ).length;

  return (
    <div>
      <h1 className="text-2xl font-bold text-white/90">Overview</h1>
      <p className="mt-1 text-sm text-white/40">
        Your OpenClaw Cloud instance at a glance.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Agent status */}
        <div className="animate-fade-up rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-white/50">Agent Status</h2>
            <StatusBadge status={box.status} />
          </div>
          <div className="mt-4 flex items-center gap-3">
            <span
              className={`inline-block h-3 w-3 rounded-full ${statusColor} animate-pulse-glow`}
            />
            <span className="text-lg font-semibold capitalize text-white/90">
              {box.status}
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-white/40">Uptime</span>
            <span className="font-medium text-white/70">
              {timeAgo(box.activated_at)}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-sm">
            <span className="text-white/40">Tier</span>
            <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium capitalize text-emerald-400">
              {box.tier}
            </span>
          </div>
        </div>

        {/* Token usage */}
        <div className="animate-fade-up delay-100 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">
            Token Usage
          </h2>
          <UsageGauge used={box.tokens_used} limit={box.tokens_limit} />
        </div>

        {/* Quick stats */}
        <div className="animate-fade-up delay-200 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">
            Quick Stats
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-blue-500/10 p-2">
                <Globe className="h-4 w-4 text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white/90">
                  {analytics?.browser_sessions.session_count ?? 0}
                </p>
                <p className="text-xs text-white/40">Browser Sessions</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-purple-500/10 p-2">
                <Plug className="h-4 w-4 text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white/90">
                  {connectedCount}
                </p>
                <p className="text-xs text-white/40">Connections</p>
              </div>
            </div>
          </div>
        </div>

        {/* Configuration summary */}
        <div className="animate-fade-up delay-300 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">
            Configuration
          </h2>
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <Cpu className="h-4 w-4 text-white/30" />
              <span className="text-white/40">Model</span>
              <span className="ml-auto font-medium text-white/80">
                {box.model}
              </span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <Brain className="h-4 w-4 text-white/30" />
              <span className="text-white/40">Thinking</span>
              <span className="ml-auto font-medium capitalize text-white/80">
                {box.thinking_level}
              </span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <Languages className="h-4 w-4 text-white/30" />
              <span className="text-white/40">Language</span>
              <span className="ml-auto font-medium uppercase text-white/80">
                {box.language}
              </span>
            </div>
            {box.niche && (
              <div className="flex items-center gap-3 text-sm">
                <Target className="h-4 w-4 text-white/30" />
                <span className="text-white/40">Niche</span>
                <span className="ml-auto font-medium text-white/80">
                  {box.niche}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="animate-fade-up delay-400 mt-6 flex flex-wrap gap-3">
        <Link
          href="/dashboard/connections"
          className="inline-flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm font-medium text-white/70 transition-all hover:border-emerald-500/30 hover:text-emerald-400"
        >
          Manage Connections
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
        <Link
          href="/dashboard/analytics"
          className="inline-flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm font-medium text-white/70 transition-all hover:border-emerald-500/30 hover:text-emerald-400"
        >
          View Analytics
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
        <Link
          href="/dashboard/settings"
          className="inline-flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-sm font-medium text-white/70 transition-all hover:border-emerald-500/30 hover:text-emerald-400"
        >
          Settings
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
