"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, type Box, type UpdateBoxRequest } from "@/lib/api";
import { Link } from "@/i18n/navigation";
import { Save, ExternalLink } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuth();
  const [box, setBox] = useState<Box | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Editable fields
  const [model, setModel] = useState("");
  const [thinkingLevel, setThinkingLevel] = useState("");
  const [language, setLanguage] = useState("");
  const [telegramIds, setTelegramIds] = useState("");

  useEffect(() => {
    api
      .getBox("me")
      .then((b) => {
        setBox(b);
        setModel(b.model);
        setThinkingLevel(b.thinking_level);
        setLanguage(b.language);
        setTelegramIds(b.telegram_user_ids.join(", "));
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const parsedIds = telegramIds
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean)
        .map(Number)
        .filter((n) => !isNaN(n));

      const update: UpdateBoxRequest = {
        model,
        thinking_level: thinkingLevel,
        language,
        telegram_user_ids: parsedIds,
      };

      const updated = await api.updateBox(update);
      setBox(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div>
        <div className="skeleton mb-8 h-8 w-32" />
        <div className="space-y-6">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton h-32 w-full rounded-xl" />
          ))}
        </div>
      </div>
    );
  }

  if (!box) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
        <h2 className="font-semibold text-red-400">Could not load settings</h2>
        <p className="mt-1 text-sm text-white/50">
          {error ?? "No active instance found."}
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-white/90">Settings</h1>
      <p className="mt-1 text-sm text-white/40">
        Manage your OpenClaw Cloud configuration.
      </p>

      {error && (
        <div className="animate-fade-up mt-4 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {success && (
        <div className="animate-fade-up mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
          <p className="text-sm text-emerald-400">Settings saved successfully.</p>
        </div>
      )}

      <div className="mt-8 space-y-6">
        {/* Account info */}
        <div className="animate-fade-up rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">Account</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/40">Email</span>
              <span className="font-medium text-white/80">
                {user?.email ?? "—"}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-white/40">Name</span>
              <span className="font-medium text-white/80">
                {user?.name ?? "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Tier */}
        <div className="animate-fade-up delay-100 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">
            Subscription
          </h2>
          <div className="flex items-center justify-between">
            <div>
              <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-sm font-medium capitalize text-emerald-400">
                {box.tier}
              </span>
            </div>
            <Link
              href="/billing"
              className="inline-flex items-center gap-1.5 text-sm text-white/50 transition-colors hover:text-emerald-400"
            >
              Manage Billing
              <ExternalLink className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Editable config */}
        <div className="animate-fade-up delay-200 rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 card-glow">
          <h2 className="mb-4 text-sm font-medium text-white/50">
            Configuration
          </h2>
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-sm text-white/40">
                Model
              </label>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white/90 outline-none transition-colors focus:border-emerald-500/50"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm text-white/40">
                Thinking Level
              </label>
              <select
                value={thinkingLevel}
                onChange={(e) => setThinkingLevel(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white/90 outline-none transition-colors focus:border-emerald-500/50"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm text-white/40">
                Language
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white/90 outline-none transition-colors focus:border-emerald-500/50"
              >
                <option value="en">English</option>
                <option value="pt">Portuguese</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm text-white/40">
                Telegram User IDs
              </label>
              <input
                type="text"
                value={telegramIds}
                onChange={(e) => setTelegramIds(e.target.value)}
                placeholder="e.g. 12345, 67890"
                className="w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-white/90 outline-none transition-colors focus:border-emerald-500/50"
              />
              <p className="mt-1 text-xs text-white/30">
                Comma-separated Telegram user IDs
              </p>
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-black transition-all hover:bg-emerald-400 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
