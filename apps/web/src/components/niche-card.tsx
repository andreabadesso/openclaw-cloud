import { cn } from "@/lib/utils";

interface NicheCardProps {
  slug: string;
  name: string;
  tagline: string;
  icon: string;
  available: boolean;
  features?: string[];
  comingSoonLabel: string;
  ctaLabel: string;
}

export function NicheCard({
  name,
  tagline,
  icon,
  available,
  features,
  comingSoonLabel,
  ctaLabel,
}: NicheCardProps) {
  return (
    <div
      className={cn(
        "group relative flex flex-col rounded-xl border p-6 transition-all duration-300",
        available
          ? "card-highlight border-emerald-500/20 bg-[#111]/80"
          : "card-glow border-white/[0.06] bg-[#111]/50 opacity-60 hover:opacity-80",
      )}
    >
      {/* Active indicator */}
      {available && (
        <div className="absolute -top-px left-6 right-6 h-px bg-gradient-to-r from-transparent via-emerald-400/60 to-transparent" />
      )}

      <div className="flex items-center gap-4">
        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-lg text-2xl",
            available
              ? "bg-emerald-500/10 shadow-[inset_0_1px_0_rgba(16,185,129,0.1)]"
              : "bg-white/[0.03]",
          )}
        >
          {icon}
        </div>
        <div>
          <h3 className="text-[15px] font-semibold text-white/90">{name}</h3>
          <p className="mt-0.5 text-[13px] text-white/40">{tagline}</p>
        </div>
      </div>

      {features && features.length > 0 && (
        <ul className="mt-5 flex-1 space-y-2.5">
          {features.map((f) => (
            <li
              key={f}
              className="flex items-start gap-2.5 text-[13px] text-white/50"
            >
              <svg
                className={cn(
                  "mt-0.5 h-3.5 w-3.5 shrink-0",
                  available ? "text-emerald-400" : "text-white/20",
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
      )}

      <div className="mt-6">
        {available ? (
          <a
            href="/onboarding"
            className="btn-cta inline-flex w-full items-center justify-center rounded-lg bg-emerald-500 px-4 py-2.5 text-[13px] font-medium text-black transition-all hover:bg-emerald-400"
          >
            {ctaLabel}
          </a>
        ) : (
          <span className="inline-flex w-full items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 text-[13px] font-medium text-white/30">
            {comingSoonLabel}
          </span>
        )}
      </div>
    </div>
  );
}
