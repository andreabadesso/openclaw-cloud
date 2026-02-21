import { cn } from "@/lib/utils";

interface PricingCardProps {
  name: string;
  price: number;
  features: string[];
  highlighted?: boolean;
}

export function PricingCard({
  name,
  price,
  features,
  highlighted = false,
}: PricingCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col rounded-lg border p-6",
        highlighted
          ? "border-primary bg-primary/5 shadow-lg"
          : "border-border bg-card",
      )}
    >
      <h3 className="text-lg font-semibold">{name}</h3>
      <div className="mt-4 flex items-baseline gap-1">
        <span className="text-4xl font-bold">${price}</span>
        <span className="text-muted-foreground">/month</span>
      </div>
      <ul className="mt-6 flex-1 space-y-3">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <svg
              className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            {f}
          </li>
        ))}
      </ul>
      <a
        href="/onboarding"
        className={cn(
          "mt-8 inline-flex items-center justify-center rounded-md px-4 py-2.5 text-sm font-medium transition-colors",
          highlighted
            ? "bg-primary text-primary-foreground hover:bg-primary/90"
            : "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        )}
      >
        Get Started
      </a>
    </div>
  );
}
