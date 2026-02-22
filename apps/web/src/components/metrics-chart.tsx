interface MetricsChartProps {
  data: { value: number; ts: string }[];
  maxValue?: number;
  limitValue?: number;
  color?: string;
  formatValue?: (v: number) => string;
  label: string;
  height?: number;
}

export function MetricsChart({
  data,
  maxValue,
  limitValue,
  color = "#3b82f6",
  formatValue = (v) => String(v),
  label,
  height = 160,
}: MetricsChartProps) {
  const W = 400;
  const H = height;
  const PAD = { top: 8, right: 8, bottom: 24, left: 8 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border bg-card p-6" style={{ minHeight: H }}>
        <p className="text-sm text-muted-foreground">No {label.toLowerCase()} data yet</p>
      </div>
    );
  }

  const values = data.map((d) => d.value);
  const ceil = maxValue ?? (Math.max(...values) * 1.1 || 1);

  const points = data.map((d, i) => {
    const x = PAD.left + (i / Math.max(data.length - 1, 1)) * plotW;
    const y = PAD.top + plotH - (d.value / ceil) * plotH;
    return `${x},${y}`;
  });

  const linePoints = points.join(" ");
  const areaPoints = `${PAD.left},${PAD.top + plotH} ${linePoints} ${PAD.left + plotW},${PAD.top + plotH}`;

  const limitY = limitValue != null ? PAD.top + plotH - (limitValue / ceil) * plotH : null;

  const latest = values[values.length - 1];

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">{formatValue(latest)}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none">
        <polygon points={areaPoints} fill={color} opacity="0.15" />
        <polyline points={linePoints} fill="none" stroke={color} strokeWidth="2" />
        {limitY != null && (
          <line
            x1={PAD.left}
            y1={limitY}
            x2={PAD.left + plotW}
            y2={limitY}
            stroke="#ef4444"
            strokeWidth="1.5"
            strokeDasharray="6 4"
          />
        )}
      </svg>
      {limitValue != null && (
        <p className="mt-1 text-right text-xs text-muted-foreground">
          Limit: {formatValue(limitValue)}
        </p>
      )}
    </div>
  );
}
