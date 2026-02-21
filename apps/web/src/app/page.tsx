import { PricingCard } from "@/components/pricing-card";

const steps = [
  {
    num: "1",
    title: "Chat",
    desc: "Tell our onboarding agent what you need. No forms, no config files.",
  },
  {
    num: "2",
    title: "Pay",
    desc: "Pick a plan and check out with Stripe. Takes 30 seconds.",
  },
  {
    num: "3",
    title: "Code",
    desc: "Your personal AI agent is live on Telegram within seconds.",
  },
];

const tiers = [
  {
    name: "Starter",
    price: 19,
    features: [
      "1M tokens / month",
      "1 Telegram user",
      "Medium thinking level",
      "Community support",
    ],
  },
  {
    name: "Pro",
    price: 49,
    highlighted: true,
    features: [
      "5M tokens / month",
      "1 Telegram user",
      "Medium thinking level",
      "Custom system prompt",
      "Email support (48h)",
    ],
  },
  {
    name: "Team",
    price: 129,
    features: [
      "20M tokens / month",
      "Up to 10 Telegram users",
      "High thinking level",
      "Custom system prompt",
      "Email support (24h)",
    ],
  },
];

export default function HomePage() {
  return (
    <>
      {/* Hero */}
      <section className="flex flex-col items-center px-4 pb-20 pt-24 text-center">
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
          Your AI Coding Agent.{" "}
          <span className="text-emerald-500">Zero Setup.</span>
        </h1>
        <p className="mt-6 max-w-xl text-lg text-muted-foreground">
          A fully managed AI coding agent delivered via Telegram. Just chat,
          pay, and start coding — no servers, no config, no hassle.
        </p>
        <a
          href="/onboarding"
          className="mt-8 inline-flex items-center rounded-md bg-emerald-600 px-6 py-3 text-sm font-medium text-white hover:bg-emerald-700"
        >
          Get Started Free
        </a>
      </section>

      {/* How It Works */}
      <section className="border-t bg-muted/30 px-4 py-20">
        <div className="mx-auto max-w-4xl">
          <h2 className="text-center text-3xl font-bold">How It Works</h2>
          <div className="mt-12 grid gap-8 sm:grid-cols-3">
            {steps.map((s) => (
              <div key={s.num} className="text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600 text-lg font-bold text-white">
                  {s.num}
                </div>
                <h3 className="mt-4 text-xl font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="px-4 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-center text-3xl font-bold">
            Simple, Transparent Pricing
          </h2>
          <p className="mt-4 text-center text-muted-foreground">
            No surprise bills. No overages. Upgrade or downgrade anytime.
          </p>
          <div className="mt-12 grid gap-6 sm:grid-cols-3">
            {tiers.map((t) => (
              <PricingCard key={t.name} {...t} />
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t bg-muted/30 px-4 py-20 text-center">
        <h2 className="text-3xl font-bold">Ready to Start Coding?</h2>
        <p className="mt-4 text-muted-foreground">
          Set up your personal AI coding agent in under a minute.
        </p>
        <a
          href="/onboarding"
          className="mt-8 inline-flex items-center rounded-md bg-emerald-600 px-6 py-3 text-sm font-medium text-white hover:bg-emerald-700"
        >
          Get Started
        </a>
      </section>
    </>
  );
}
