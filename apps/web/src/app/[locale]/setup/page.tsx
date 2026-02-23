"use client";

import { useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const NICHES = [
  { slug: "general", icon: "🤖", available: true },
  { slug: "pharmacy", icon: "💊", available: true },
  { slug: "legal", icon: "⚖️", available: false },
  { slug: "realestate", icon: "🏠", available: false },
  { slug: "accounting", icon: "📊", available: false },
];

const TIERS = [
  {
    key: "starter" as const,
    price: 19,
    features: [
      "1M tokens/month",
      "1 Telegram user",
      "Medium thinking",
      "Community support",
    ],
  },
  {
    key: "pro" as const,
    price: 49,
    highlighted: true,
    features: [
      "5M tokens/month",
      "1 Telegram user",
      "Medium thinking",
      "Custom prompt",
      "Email support (48h)",
    ],
  },
  {
    key: "team" as const,
    price: 129,
    features: [
      "20M tokens/month",
      "Up to 10 users",
      "High thinking",
      "Custom prompt",
      "Email support (24h)",
    ],
  },
];

const TOTAL_STEPS = 5;

function StepDots({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: TOTAL_STEPS }, (_, i) => (
        <div
          key={i}
          className={cn(
            "h-2 w-2 rounded-full transition-all duration-300",
            i === current
              ? "w-6 bg-emerald-400"
              : i < current
                ? "bg-emerald-400/40"
                : "bg-white/10",
          )}
        />
      ))}
    </div>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
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
  );
}

export default function SetupPage() {
  const t = useTranslations("setup");
  const router = useRouter();
  const { user, isLoading, isAuthenticated } = useAuth();

  const [step, setStep] = useState(0);
  const [niche, setNiche] = useState("general");
  const [botToken, setBotToken] = useState("");
  const [userId, setUserId] = useState("");
  const [tier, setTier] = useState("pro");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canContinueTelegram = botToken.trim().length > 0 && userId.trim().length > 0;

  const next = useCallback(() => setStep((s) => Math.min(s + 1, TOTAL_STEPS - 1)), []);
  const prev = useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await api.setup({
        telegram_bot_token: botToken.trim(),
        telegram_user_id: Number(userId.trim()),
        tier,
        niche: niche === "general" ? undefined : niche,
        model: "claude-sonnet-4-20250514",
        thinking_level: tier === "team" ? "high" : "medium",
        language: "en",
      });
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  // Auth guards
  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated) {
    router.replace("/login");
    return null;
  }

  if (user?.has_box) {
    router.replace("/dashboard");
    return null;
  }

  return (
    <section className="flex min-h-[80vh] flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-2xl">
        <div className="mb-8">
          <StepDots current={step} />
        </div>

        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-8 sm:p-10">
          {/* Step 0: Welcome */}
          {step === 0 && (
            <div className="animate-fade-up text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10">
                <span className="text-3xl">🚀</span>
              </div>
              <h1 className="mt-6 text-2xl font-bold text-white sm:text-3xl">
                {t("welcome.title")}
              </h1>
              <p className="mt-3 text-[15px] text-white/45">
                {t("welcome.subtitle")}
              </p>
              <button
                onClick={next}
                className="btn-cta mt-10 inline-flex items-center rounded-xl bg-emerald-500 px-8 py-3 text-[14px] font-semibold text-black transition-all hover:bg-emerald-400 hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.4)]"
              >
                {t("welcome.cta")}
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
              </button>
            </div>
          )}

          {/* Step 1: Choose Niche */}
          {step === 1 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("niche.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("niche.subtitle")}
              </p>

              <div className="mt-8 grid gap-3 sm:grid-cols-2">
                {NICHES.map((n) => (
                  <button
                    key={n.slug}
                    disabled={!n.available}
                    onClick={() => n.available && setNiche(n.slug)}
                    className={cn(
                      "relative flex items-center gap-4 rounded-xl border p-4 text-left transition-all duration-200",
                      n.available
                        ? niche === n.slug
                          ? "border-emerald-500/50 bg-emerald-500/[0.06] shadow-[0_0_20px_-5px_rgba(16,185,129,0.15)]"
                          : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]"
                        : "cursor-not-allowed border-white/[0.04] bg-white/[0.01] opacity-50",
                    )}
                  >
                    <div
                      className={cn(
                        "flex h-10 w-10 items-center justify-center rounded-lg text-xl",
                        n.available && niche === n.slug
                          ? "bg-emerald-500/10"
                          : "bg-white/[0.03]",
                      )}
                    >
                      {n.icon}
                    </div>
                    <div className="flex-1">
                      <span className="text-[14px] font-medium text-white/90">
                        {t(`niche.${n.slug}`)}
                      </span>
                    </div>
                    {n.available && niche === n.slug && (
                      <CheckIcon className="h-4 w-4 text-emerald-400" />
                    )}
                    {!n.available && (
                      <span className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[11px] text-white/30">
                        {t("niche.comingSoon")}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={prev}
                  className="text-[13px] text-white/40 transition-colors hover:text-white/70"
                >
                  {t("back")}
                </button>
                <button
                  onClick={next}
                  className="btn-cta inline-flex items-center rounded-xl bg-emerald-500 px-6 py-2.5 text-[13px] font-semibold text-black transition-all hover:bg-emerald-400"
                >
                  {t("continue")}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Telegram Setup */}
          {step === 2 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("telegram.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("telegram.subtitle")}
              </p>

              <div className="mt-8 space-y-6">
                {/* Bot Token */}
                <div>
                  <label className="block text-[13px] font-medium text-white/70">
                    {t("telegram.botTokenLabel")}
                  </label>
                  <div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                    <ol className="mb-4 space-y-1 text-[12px] text-white/30">
                      <li>{t("telegram.botStep1")}</li>
                      <li>{t("telegram.botStep2")}</li>
                      <li>{t("telegram.botStep3")}</li>
                    </ol>
                    <input
                      type="text"
                      value={botToken}
                      onChange={(e) => setBotToken(e.target.value)}
                      placeholder={t("telegram.botTokenPlaceholder")}
                      className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-[13px] text-white/90 placeholder-white/20 outline-none transition-colors focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/20"
                    />
                  </div>
                </div>

                {/* User ID */}
                <div>
                  <label className="block text-[13px] font-medium text-white/70">
                    {t("telegram.userIdLabel")}
                  </label>
                  <div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                    <p className="mb-4 text-[12px] text-white/30">
                      {t("telegram.userIdHint")}
                    </p>
                    <input
                      type="text"
                      value={userId}
                      onChange={(e) => setUserId(e.target.value)}
                      placeholder={t("telegram.userIdPlaceholder")}
                      className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-[13px] text-white/90 placeholder-white/20 outline-none transition-colors focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/20"
                    />
                  </div>
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={prev}
                  className="text-[13px] text-white/40 transition-colors hover:text-white/70"
                >
                  {t("back")}
                </button>
                <button
                  onClick={next}
                  disabled={!canContinueTelegram}
                  className={cn(
                    "btn-cta inline-flex items-center rounded-xl px-6 py-2.5 text-[13px] font-semibold transition-all",
                    canContinueTelegram
                      ? "bg-emerald-500 text-black hover:bg-emerald-400"
                      : "cursor-not-allowed bg-white/[0.06] text-white/30",
                  )}
                >
                  {t("continue")}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Choose Tier */}
          {step === 3 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("tier.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("tier.subtitle")}
              </p>

              <div className="mt-8 grid gap-4 sm:grid-cols-3">
                {TIERS.map((t_) => (
                  <button
                    key={t_.key}
                    onClick={() => setTier(t_.key)}
                    className={cn(
                      "relative flex flex-col rounded-xl border p-5 text-left transition-all duration-200",
                      tier === t_.key
                        ? "border-emerald-500/50 bg-emerald-500/[0.06] shadow-[0_0_20px_-5px_rgba(16,185,129,0.15)]"
                        : t_.highlighted
                          ? "border-emerald-500/20 bg-[#111]/80 hover:border-emerald-500/30"
                          : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]",
                    )}
                  >
                    {t_.highlighted && (
                      <div className="absolute -top-px left-4 right-4 h-px bg-gradient-to-r from-transparent via-emerald-400/60 to-transparent" />
                    )}

                    <div className="flex items-center justify-between">
                      <span className="text-[14px] font-semibold text-white/90">
                        {t(`tier.${t_.key}.name`)}
                      </span>
                      {t_.highlighted && (
                        <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-400">
                          Popular
                        </span>
                      )}
                    </div>

                    <div className="mt-3 flex items-baseline gap-1">
                      <span className="text-2xl font-bold text-white">
                        ${t_.price}
                      </span>
                      <span className="text-[12px] text-white/30">/mo</span>
                    </div>

                    <div className="my-4 h-px bg-white/[0.06]" />

                    <ul className="flex-1 space-y-2">
                      {t_.features.map((f) => (
                        <li
                          key={f}
                          className="flex items-start gap-2 text-[12px] text-white/45"
                        >
                          <CheckIcon
                            className={cn(
                              "mt-0.5 h-3 w-3 shrink-0",
                              tier === t_.key
                                ? "text-emerald-400"
                                : "text-white/20",
                            )}
                          />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>

                    {tier === t_.key && (
                      <div className="mt-4 flex items-center justify-center">
                        <CheckIcon className="h-4 w-4 text-emerald-400" />
                        <span className="ml-1 text-[12px] font-medium text-emerald-400">
                          {t("tier.selected")}
                        </span>
                      </div>
                    )}
                  </button>
                ))}
              </div>

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={prev}
                  className="text-[13px] text-white/40 transition-colors hover:text-white/70"
                >
                  {t("back")}
                </button>
                <button
                  onClick={next}
                  className="btn-cta inline-flex items-center rounded-xl bg-emerald-500 px-6 py-2.5 text-[13px] font-semibold text-black transition-all hover:bg-emerald-400"
                >
                  {t("continue")}
                </button>
              </div>
            </div>
          )}

          {/* Step 4: Review & Submit */}
          {step === 4 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("review.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("review.subtitle")}
              </p>

              <div className="mt-8 space-y-4">
                {/* Niche summary */}
                <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                  <div>
                    <span className="text-[12px] text-white/30">
                      {t("review.nicheLabel")}
                    </span>
                    <p className="mt-0.5 text-[14px] font-medium text-white/90">
                      {NICHES.find((n) => n.slug === niche)?.icon}{" "}
                      {t(`niche.${niche}`)}
                    </p>
                  </div>
                  <button
                    onClick={() => setStep(1)}
                    className="text-[12px] text-emerald-400/70 hover:text-emerald-400"
                  >
                    {t("review.change")}
                  </button>
                </div>

                {/* Telegram summary */}
                <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                  <div>
                    <span className="text-[12px] text-white/30">
                      {t("review.telegramLabel")}
                    </span>
                    <p className="mt-0.5 text-[14px] font-medium text-white/90">
                      {t("review.telegramConfigured")}
                    </p>
                  </div>
                  <button
                    onClick={() => setStep(2)}
                    className="text-[12px] text-emerald-400/70 hover:text-emerald-400"
                  >
                    {t("review.change")}
                  </button>
                </div>

                {/* Tier summary */}
                <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                  <div>
                    <span className="text-[12px] text-white/30">
                      {t("review.tierLabel")}
                    </span>
                    <p className="mt-0.5 text-[14px] font-medium text-white/90">
                      {t(`tier.${tier}.name`)} — $
                      {TIERS.find((t_) => t_.key === tier)?.price}/mo
                    </p>
                  </div>
                  <button
                    onClick={() => setStep(3)}
                    className="text-[12px] text-emerald-400/70 hover:text-emerald-400"
                  >
                    {t("review.change")}
                  </button>
                </div>
              </div>

              {error && (
                <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/[0.06] px-4 py-3 text-[13px] text-red-400">
                  {error}
                </div>
              )}

              <div className="mt-8 flex items-center justify-between">
                <button
                  onClick={prev}
                  className="text-[13px] text-white/40 transition-colors hover:text-white/70"
                >
                  {t("back")}
                </button>
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className={cn(
                    "btn-cta inline-flex items-center rounded-xl bg-emerald-500 px-8 py-3 text-[14px] font-semibold text-black transition-all hover:bg-emerald-400 hover:shadow-[0_0_30px_-5px_rgba(16,185,129,0.4)]",
                    submitting && "cursor-not-allowed opacity-70",
                  )}
                >
                  {submitting ? (
                    <>
                      <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-black/30 border-t-black" />
                      {t("review.creating")}
                    </>
                  ) : (
                    t("review.submit")
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
