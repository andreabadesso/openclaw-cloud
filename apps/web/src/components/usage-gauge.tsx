import { cn } from "@/lib/utils";

interface UsageGaugeProps {
  used: number;
  limit: number;
  label?: string;
}

export function UsageGauge({ used, limit, label = "Token Usage" }: UsageGaugeProps) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const isHigh = pct >= 80;
  const isCritical = pct >= 95;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">
          {(used / 1_000_000).toFixed(2)}M / {(limit / 1_000_000).toFixed(1)}M tokens
        </span>
      </div>
      <div className="h-3 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className={cn(
            "h-full rounded-full transition-all",
            isCritical
              ? "bg-red-500"
              : isHigh
                ? "bg-amber-500"
                : "bg-emerald-500",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-right text-xs text-muted-foreground">
        {pct.toFixed(1)}% used
      </p>
    </div>
  );
}
