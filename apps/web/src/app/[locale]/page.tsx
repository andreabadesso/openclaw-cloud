"use client";

import { useTranslations } from "next-intl";
import { NicheCard } from "@/components/niche-card";
import { PricingCard } from "@/components/pricing-card";
import { useAuth } from "@/lib/auth";
import { Link } from "@/i18n/navigation";

const NICHES = [
  { slug: "pharmacy", icon: "💊", available: true },
  { slug: "legal", icon: "⚖️", available: false },
  { slug: "realestate", icon: "🏠", available: false },
  { slug: "accounting", icon: "📊", available: false },
] as const;

const TIERS = [
  { key: "starter" as const, price: 19 },
  { key: "pro" as const, price: 49, highlighted: true },
  { key: "team" as const, price: 129 },
];

export default function HomePage() {
  const t = useTranslations();
  const { isAuthenticated } = useAuth();

  const ctaHref = isAuthenticated ? "/dashboard" : "/login";
  const ctaText = isAuthenticated ? t("header.dashboard") : t("hero.cta");

  return (
    <>
      {/* ═══════════ HERO ═══════════ */}
      <section className="relative flex flex-col items-center overflow-hidden px-6 pb-32 pt-40">
        {/* Radial glow */}
        <div className="hero-glow" />

        {/* Badge */}
        <div className="animate-fade-up relative z-10 mb-8 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/[0.06] px-4 py-1.5">
          <span className="animate-pulse-glow h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <span className="text-[12px] font-medium tracking-wide text-emerald-400/90">
            Telegram + IA
          </span>
        </div>

        {/* Heading */}
        <h1 className="animate-fade-up delay-100 relative z-10 max-w-3xl text-center text-[clamp(2.25rem,5vw,4rem)] font-bold leading-[1.08] tracking-tight text-white">
          {t("hero.title")}
          <br />
          <span className="text-gradient">{t("hero.titleAccent")}</span>
        </h1>

        {/* Subtitle */}
        <p className="animate-fade-up delay-200 relative z-10 mt-6 max-w-lg text-center text-[15px] leading-relaxed text-white/45">
          {t("hero.subtitle")}
        </p>

        {/* CTA */}
        <div className="animate-fade-up delay-300 relative z-10 mt-10 flex items-center gap-4">
          <Link
            href={ctaHref}
            className="btn-cta inline-flex items-center rounded-xl bg-emerald-500 px-7 py-3 text-[14px] font-semibold text-black transition-all hover:bg-emerald-400 hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.4)]"
          >
            {ctaText}
            <svg
              className="ml-2 h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 7l5 5m0 0l-5 5m5-5H6"
              />
            </svg>
          </Link>
        </div>

        {/* Bottom fade */}
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#0a0a0a] to-transparent" />
      </section>

      {/* ═══════════ DIVIDER ═══════════ */}
      <div className="divider-gradient mx-auto max-w-4xl" />

      {/* ═══════════ NICHE CATALOG ═══════════ */}
      <section className="px-6 py-28">
        <div className="mx-auto max-w-5xl">
          <div className="text-center">
            <span className="text-[12px] font-medium uppercase tracking-[0.2em] text-emerald-400/70">
              Marketplace
            </span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              {t("niches.sectionTitle")}
            </h2>
            <p className="mx-auto mt-4 max-w-md text-[15px] text-white/40">
              {t("niches.sectionSubtitle")}
            </p>
          </div>

          <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {NICHES.map((niche) => (
              <NicheCard
                key={niche.slug}
                slug={niche.slug}
                name={t(`niches.${niche.slug}.name`)}
                tagline={t(`niches.${niche.slug}.tagline`)}
                icon={niche.icon}
                available={niche.available}
                features={t.raw(`niches.${niche.slug}.features`) as string[]}
                comingSoonLabel={t("niches.comingSoon")}
                ctaLabel={t("niches.cta")}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ DIVIDER ═══════════ */}
      <div className="divider-gradient mx-auto max-w-4xl" />

      {/* ═══════════ HOW IT WORKS ═══════════ */}
      <section className="px-6 py-28">
        <div className="mx-auto max-w-4xl">
          <div className="text-center">
            <span className="text-[12px] font-medium uppercase tracking-[0.2em] text-emerald-400/70">
              3 steps
            </span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              {t("howItWorks.title")}
            </h2>
          </div>

          <div className="mt-16 grid gap-0 sm:grid-cols-3">
            {(["step1", "step2", "step3"] as const).map((step, i) => (
              <div
                key={step}
                className={`relative flex flex-col items-center text-center px-6 ${i < 2 ? "step-connector" : ""}`}
              >
                {/* Step number */}
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.06]">
                  <span className="text-lg font-bold text-emerald-400">
                    {i + 1}
                  </span>
                </div>

                <h3 className="mt-5 text-[16px] font-semibold text-white/90">
                  {t(`howItWorks.${step}.title`)}
                </h3>
                <p className="mt-2 text-[13px] leading-relaxed text-white/40">
                  {t(`howItWorks.${step}.desc`)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ DIVIDER ═══════════ */}
      <div className="divider-gradient mx-auto max-w-4xl" />

      {/* ═══════════ PRICING ═══════════ */}
      <section id="pricing" className="px-6 py-28">
        <div className="mx-auto max-w-5xl">
          <div className="text-center">
            <span className="text-[12px] font-medium uppercase tracking-[0.2em] text-emerald-400/70">
              Pricing
            </span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              {t("pricing.title")}
            </h2>
            <p className="mx-auto mt-4 max-w-md text-[15px] text-white/40">
              {t("pricing.subtitle")}
            </p>
          </div>

          <div className="mt-16 grid gap-5 sm:grid-cols-3">
            {TIERS.map((tier) => (
              <PricingCard
                key={tier.key}
                name={t(`pricing.${tier.key}.name`)}
                price={tier.price}
                features={t.raw(`pricing.${tier.key}.features`) as string[]}
                highlighted={tier.highlighted}
                ctaLabel={t("pricing.cta")}
                perMonthLabel={t("pricing.perMonth")}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ FINAL CTA ═══════════ */}
      <section className="relative overflow-hidden px-6 py-28">
        {/* Background glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] rounded-full bg-emerald-500/[0.04] blur-[100px] pointer-events-none" />

        <div className="relative mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            {t("cta.title")}
          </h2>
          <p className="mt-4 text-[15px] text-white/40">
            {t("cta.subtitle")}
          </p>
          <Link
            href={ctaHref}
            className="btn-cta mt-10 inline-flex items-center rounded-xl bg-emerald-500 px-8 py-3.5 text-[14px] font-semibold text-black transition-all hover:bg-emerald-400 hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.4)]"
          >
            {isAuthenticated ? t("header.dashboard") : t("cta.button")}
            <svg
              className="ml-2 h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 7l5 5m0 0l-5 5m5-5H6"
              />
            </svg>
          </Link>
        </div>
      </section>

      {/* ═══════════ FOOTER ═══════════ */}
      <footer className="border-t border-white/[0.04] px-6 py-8">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <span className="text-[12px] text-white/20">
            &copy; 2026 OpenClaw Cloud
          </span>
          <div className="flex items-center gap-1">
            <span className="text-[12px] text-white/20">
              OpenClaw
            </span>
            <span className="text-[12px] text-gradient">Cloud</span>
          </div>
        </div>
      </footer>
    </>
  );
}
