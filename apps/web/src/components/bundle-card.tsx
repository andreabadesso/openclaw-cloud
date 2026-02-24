import { cn } from "@/lib/utils";
import type { BundleListItem } from "@/lib/api";

interface BundleCardProps {
  bundle: Pick<BundleListItem, "id" | "slug" | "name" | "description" | "icon" | "color" | "providers" | "skills" | "sort_order">;
  ctaLabel: string;
}

export function BundleCard({ bundle, ctaLabel }: BundleCardProps) {
  const color = bundle.color || "#10B981";

  return (
    <div
      className="group relative flex flex-col rounded-xl border border-white/[0.06] bg-[#111]/80 p-6 transition-all duration-300 hover:border-white/10"
      style={{ "--bundle-color": color } as React.CSSProperties}
    >
      <div className="absolute -top-px left-6 right-6 h-px" style={{ background: `linear-gradient(to right, transparent, ${color}60, transparent)` }} />

      <div className="flex items-center gap-4">
        <div
          className="flex h-12 w-12 items-center justify-center rounded-lg text-2xl"
          style={{ background: `${color}18`, boxShadow: `inset 0 1px 0 ${color}20` }}
        >
          {bundle.icon}
        </div>
        <div>
          <h3 className="text-[15px] font-semibold text-white/90">{bundle.name}</h3>
          <p className="mt-0.5 text-[13px] text-white/40">{bundle.description}</p>
        </div>
      </div>

      {bundle.skills && bundle.skills.length > 0 && (
        <ul className="mt-5 flex-1 space-y-2.5">
          {bundle.skills.slice(0, 4).map((skill) => (
            <li key={skill} className="flex items-start gap-2.5 text-[13px] text-white/50">
              <svg className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              <span className="capitalize">{skill.replace(/-/g, " ")}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6">
        <a
          href={`/onboarding?bundle=${bundle.slug}`}
          className={cn(
            "inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-[13px] font-medium transition-all",
          )}
          style={{ background: color, color: "#000" }}
        >
          {ctaLabel}
        </a>
      </div>
    </div>
  );
}
