import { useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { useRouter } from "@/i18n/navigation";
import { useAuth } from "@/lib/auth";
import { api, type BundleListItem } from "@/lib/api";
import { cn } from "@/lib/utils";

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

const TOTAL_STEPS = 4;

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
  const { t } = useTranslation();
  const router = useRouter();
  const [searchParams] = useSearchParams();
  const { user, isLoading, isAuthenticated } = useAuth();

  const [step, setStep] = useState(0);
  const [bundles, setBundles] = useState<BundleListItem[]>([]);
  const [selectedBundleId, setSelectedBundleId] = useState<string | null>(null);
  const [botToken, setBotToken] = useState("");
  const [userId, setUserId] = useState("");
  const [tier, setTier] = useState("pro");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getBundles().then((b) => {
      setBundles(b);
      const bundleSlug = searchParams.get("bundle");
      if (bundleSlug) {
        const match = b.find((item) => item.slug === bundleSlug);
        if (match) {
          setSelectedBundleId(match.id);
          return;
        }
      }
      if (b.length > 0 && !selectedBundleId) {
        setSelectedBundleId(b[0].id);
      }
    }).catch(() => {});
  }, []);

  const selectedBundle = bundles.find((b) => b.id === selectedBundleId);
  const canContinueTelegram = botToken.trim().length > 0 && userId.trim().length > 0;

  const next = useCallback(() => setStep((s) => Math.min(s + 1, TOTAL_STEPS - 1)), []);
  const prev = useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);

  const handleSubmit = async () => {
    if (!selectedBundleId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.setup({
        telegram_bot_token: botToken.trim(),
        telegram_user_id: Number(userId.trim()),
        tier,
        bundle_id: selectedBundleId,
      });
      router.push("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setSubmitting(false);
    }
  };

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
          {/* Step 0: Choose Agent Bundle */}
          {step === 0 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("setup.bundle.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("setup.bundle.subtitle")}
              </p>

              <div className="mt-8 grid gap-3 sm:grid-cols-2">
                {bundles.map((b) => {
                  const requiredProviders = b.providers.filter((p) => p.required);
                  return (
                    <button
                      key={b.id}
                      onClick={() => setSelectedBundleId(b.id)}
                      className={cn(
                        "relative flex flex-col gap-3 rounded-xl border p-4 text-left transition-all duration-200",
                        selectedBundleId === b.id
                          ? "border-emerald-500/50 bg-emerald-500/[0.06] shadow-[0_0_20px_-5px_rgba(16,185,129,0.15)]"
                          : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]",
                      )}
                    >
                      <div className="flex items-center gap-4">
                        <div
                          className={cn(
                            "flex h-10 w-10 items-center justify-center rounded-lg text-xl",
                            selectedBundleId === b.id
                              ? "bg-emerald-500/10"
                              : "bg-white/[0.03]",
                          )}
                        >
                          {b.icon}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-[14px] font-medium text-white/90">
                            {b.name}
                          </span>
                          {b.description && (
                            <p className="mt-0.5 text-[12px] text-white/35 truncate">
                              {b.description}
                            </p>
                          )}
                        </div>
                        {selectedBundleId === b.id && (
                          <CheckIcon className="h-4 w-4 shrink-0 text-emerald-400" />
                        )}
                      </div>

                      {(requiredProviders.length > 0 || b.skills.length > 0) && (
                        <div className="flex flex-wrap gap-1.5">
                          {requiredProviders.map((p) => (
                            <span
                              key={p.provider}
                              className="rounded-full bg-white/[0.06] px-2 py-0.5 text-[10px] capitalize text-white/50"
                            >
                              {p.provider}
                            </span>
                          ))}
                          {b.skills.map((slug) => (
                            <a
                              key={slug}
                              href={`https://clawhub.ai/skills/${slug}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400/70 hover:text-emerald-400 transition-colors"
                            >
                              {slug}
                            </a>
                          ))}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>

              {selectedBundle && selectedBundle.providers.filter(p => p.required).length > 0 && (
                <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/[0.04] px-4 py-3">
                  <p className="text-[12px] text-amber-400/80">
                    {t("setup.bundle.requiredServices")}:{" "}
                    {selectedBundle.providers
                      .filter((p) => p.required)
                      .map((p) => p.provider)
                      .join(", ")}
                  </p>
                </div>
              )}

              <div className="mt-8 flex items-center justify-end">
                <button
                  onClick={next}
                  disabled={!selectedBundleId}
                  className={cn(
                    "btn-cta inline-flex items-center rounded-xl px-6 py-2.5 text-[13px] font-semibold transition-all",
                    selectedBundleId
                      ? "bg-emerald-500 text-black hover:bg-emerald-400"
                      : "cursor-not-allowed bg-white/[0.06] text-white/30",
                  )}
                >
                  {t("setup.continue")}
                </button>
              </div>
            </div>
          )}

          {/* Step 1: Telegram Setup */}
          {step === 1 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("setup.telegram.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("setup.telegram.subtitle")}
              </p>

              <div className="mt-8 space-y-6">
                <div>
                  <label className="block text-[13px] font-medium text-white/70">
                    {t("setup.telegram.botTokenLabel")}
                  </label>
                  <div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                    <ol className="mb-4 space-y-1 text-[12px] text-white/30">
                      <li>{t("setup.telegram.botStep1")}</li>
                      <li>{t("setup.telegram.botStep2")}</li>
                      <li>{t("setup.telegram.botStep3")}</li>
                    </ol>
                    <input
                      type="text"
                      value={botToken}
                      onChange={(e) => setBotToken(e.target.value)}
                      placeholder={t("setup.telegram.botTokenPlaceholder")}
                      className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-4 py-2.5 text-[13px] text-white/90 placeholder-white/20 outline-none transition-colors focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/20"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[13px] font-medium text-white/70">
                    {t("setup.telegram.userIdLabel")}
                  </label>
                  <div className="mt-2 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                    <p className="mb-4 text-[12px] text-white/30">
                      {t("setup.telegram.userIdHint")}
                    </p>
                    <input
                      type="text"
                      value={userId}
                      onChange={(e) => setUserId(e.target.value)}
                      placeholder={t("setup.telegram.userIdPlaceholder")}
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
                  {t("setup.back")}
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
                  {t("setup.continue")}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Choose Tier */}
          {step === 2 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("setup.tier.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("setup.tier.subtitle")}
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
                        {t(`setup.tier.${t_.key}.name`)}
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
                          {t("setup.tier.selected")}
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
                  {t("setup.back")}
                </button>
                <button
                  onClick={next}
                  className="btn-cta inline-flex items-center rounded-xl bg-emerald-500 px-6 py-2.5 text-[13px] font-semibold text-black transition-all hover:bg-emerald-400"
                >
                  {t("setup.continue")}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Review & Submit */}
          {step === 3 && (
            <div className="animate-fade-up">
              <h2 className="text-xl font-bold text-white">
                {t("setup.review.title")}
              </h2>
              <p className="mt-2 text-[14px] text-white/40">
                {t("setup.review.subtitle")}
              </p>

              <div className="mt-8 space-y-4">
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="text-[12px] text-white/30">
                        {t("setup.review.bundleLabel")}
                      </span>
                      <p className="mt-0.5 text-[14px] font-medium text-white/90">
                        {selectedBundle?.icon}{" "}
                        {selectedBundle?.name}
                      </p>
                    </div>
                    <button
                      onClick={() => setStep(0)}
                      className="text-[12px] text-emerald-400/70 hover:text-emerald-400"
                    >
                      {t("setup.review.change")}
                    </button>
                  </div>
                  {selectedBundle && selectedBundle.skills.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {selectedBundle.skills.map((slug) => (
                        <a
                          key={slug}
                          href={`https://clawhub.ai/skills/${slug}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] text-emerald-400/70 hover:text-emerald-400 transition-colors"
                        >
                          {slug}
                        </a>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                  <div>
                    <span className="text-[12px] text-white/30">
                      {t("setup.review.telegramLabel")}
                    </span>
                    <p className="mt-0.5 text-[14px] font-medium text-white/90">
                      {t("setup.review.telegramConfigured")}
                    </p>
                  </div>
                  <button
                    onClick={() => setStep(1)}
                    className="text-[12px] text-emerald-400/70 hover:text-emerald-400"
                  >
                    {t("setup.review.change")}
                  </button>
                </div>

                <div className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.02] px-5 py-4">
                  <div>
                    <span className="text-[12px] text-white/30">
                      {t("setup.review.tierLabel")}
                    </span>
                    <p className="mt-0.5 text-[14px] font-medium text-white/90">
                      {t(`setup.tier.${tier}.name`)} — $
                      {TIERS.find((t_) => t_.key === tier)?.price}/mo
                    </p>
                  </div>
                  <button
                    onClick={() => setStep(2)}
                    className="text-[12px] text-emerald-400/70 hover:text-emerald-400"
                  >
                    {t("setup.review.change")}
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
                  {t("setup.back")}
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
                      {t("setup.review.creating")}
                    </>
                  ) : (
                    t("setup.review.submit")
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
