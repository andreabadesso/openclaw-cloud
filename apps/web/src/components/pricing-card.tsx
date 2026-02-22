import { cn } from "@/lib/utils";

interface PricingCardProps {
  name: string;
  price: number;
  features: string[];
  highlighted?: boolean;
  ctaLabel?: string;
  perMonthLabel?: string;
}

export function PricingCard({
  name,
  price,
  features,
  highlighted = false,
  ctaLabel = "Get Started",
  perMonthLabel = "/month",
}: PricingCardProps) {
  return (
    <div
      className={cn(
        "group relative flex flex-col rounded-xl border p-7 transition-all duration-300",
        highlighted
          ? "card-highlight border-emerald-500/20 bg-[#111]/80"
          : "card-glow border-white/[0.06] bg-[#111]/50",
      )}
    >
      {/* Top glow line for highlighted */}
      {highlighted && (
        <div className="absolute -top-px left-8 right-8 h-px bg-gradient-to-r from-transparent via-emerald-400/60 to-transparent" />
      )}

      <div className="flex items-center justify-between">
        <h3 className="text-[15px] font-semibold text-white/90">{name}</h3>
        {highlighted && (
          <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400">
            Popular
          </span>
        )}
      </div>

      <div className="mt-5 flex items-baseline gap-1">
        <span className="text-4xl font-bold tracking-tight text-white">${price}</span>
        <span className="text-[13px] text-white/30">{perMonthLabel}</span>
      </div>

      <div className="my-6 h-px bg-white/[0.06]" />

      <ul className="flex-1 space-y-3">
        {features.map((f) => (
          <li
            key={f}
            className="flex items-start gap-2.5 text-[13px] text-white/50"
          >
            <svg
              className={cn(
                "mt-0.5 h-3.5 w-3.5 shrink-0",
                highlighted ? "text-emerald-400" : "text-white/25",
              )}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <a
        href="/onboarding"
        className={cn(
          "btn-cta mt-8 inline-flex items-center justify-center rounded-lg px-4 py-2.5 text-[13px] font-medium transition-all",
          highlighted
            ? "bg-emerald-500 text-black hover:bg-emerald-400"
            : "border border-white/[0.08] bg-white/[0.03] text-white/70 hover:border-white/[0.15] hover:bg-white/[0.06] hover:text-white/90",
        )}
      >
        {ctaLabel}
      </a>
    </div>
  );
}
