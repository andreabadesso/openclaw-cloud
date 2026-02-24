"use client";

import { useEffect, useState, type FormEvent } from "react";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";
import type { Box } from "@/lib/api";

const defaultModel = "kimi-coding/k2p5";

export default function AdminPage() {
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Form state
  const [customerEmail, setCustomerEmail] = useState("");
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [telegramUserId, setTelegramUserId] = useState("");
  const [tier, setTier] = useState<"starter" | "pro" | "team">("starter");
  const [model, setModel] = useState(defaultModel);
  const [thinkingLevel, setThinkingLevel] = useState("medium");
  const [language, setLanguage] = useState("en");
  const [bundleId, setBundleId] = useState<string>("");

  const fetchBoxes = () => {
    api
      .getBoxes()
      .then(setBoxes)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchBoxes();
  }, []);

  const handleProvision = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setMessage(null);

    try {
      await api.provision({
        customer_email: customerEmail,
        telegram_bot_token: telegramBotToken,
        telegram_user_id: parseInt(telegramUserId, 10),
        tier,
        model,
        thinking_level: thinkingLevel,
        language,
        bundle_id: bundleId,
      });
      setMessage({ type: "success", text: "Instance provisioned successfully." });
      setCustomerEmail("");
      setTelegramBotToken("");
      setTelegramUserId("");
      setTier("starter");
      setModel(defaultModel);
      setThinkingLevel("medium");
      setLanguage("en");
      setBundleId("");
      fetchBoxes();
    } catch (err) {
      setMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Provisioning failed.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleAction = async (
    boxId: string,
    action: "suspend" | "reactivate" | "destroy",
  ) => {
    if (action === "destroy" && !confirm("Destroy this instance? This cannot be undone.")) {
      return;
    }
    setActionLoading(`${boxId}-${action}`);
    try {
      await api[`${action}Box`](boxId);
      fetchBoxes();
    } catch {
      alert(`Failed to ${action} box.`);
    } finally {
      setActionLoading(null);
    }
  };

  const inputClass =
    "w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const labelClass = "block text-sm font-medium text-foreground";
  const selectClass =
    "w-full rounded-md border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <h1 className="text-2xl font-bold">Admin Panel</h1>

      {/* Provision Form */}
      <form
        onSubmit={handleProvision}
        className="mt-8 rounded-lg border bg-card p-6"
      >
        <h2 className="mb-6 text-lg font-semibold">Provision New Instance</h2>

        {message && (
          <div
            className={`mb-4 rounded-md p-3 text-sm ${
              message.type === "success"
                ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400"
                : "bg-red-500/15 text-red-700 dark:text-red-400"
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="email" className={labelClass}>
              Customer Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={customerEmail}
              onChange={(e) => setCustomerEmail(e.target.value)}
              placeholder="customer@example.com"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="bot-token" className={labelClass}>
              Telegram Bot Token
            </label>
            <input
              id="bot-token"
              type="text"
              required
              value={telegramBotToken}
              onChange={(e) => setTelegramBotToken(e.target.value)}
              placeholder="123456:ABC-DEF..."
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="user-id" className={labelClass}>
              Telegram User ID
            </label>
            <input
              id="user-id"
              type="text"
              required
              value={telegramUserId}
              onChange={(e) => setTelegramUserId(e.target.value)}
              placeholder="123456789"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="tier" className={labelClass}>
              Tier
            </label>
            <select
              id="tier"
              value={tier}
              onChange={(e) =>
                setTier(e.target.value as "starter" | "pro" | "team")
              }
              className={selectClass}
            >
              <option value="starter">Starter ($19/mo)</option>
              <option value="pro">Pro ($49/mo)</option>
              <option value="team">Team ($129/mo)</option>
            </select>
          </div>

          <div>
            <label htmlFor="bundleId" className={labelClass}>
              Bundle ID
            </label>
            <select
              id="bundleId"
              value={bundleId}
              onChange={(e) => setBundleId(e.target.value)}
              className={selectClass}
            >
              <option value="">None (generic agent)</option>
              <option value="pharmacy">Pharmacy (Farmacia)</option>
            </select>
          </div>

          <div>
            <label htmlFor="model" className={labelClass}>
              Model
            </label>
            <input
              id="model"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="thinking" className={labelClass}>
              Thinking Level
            </label>
            <select
              id="thinking"
              value={thinkingLevel}
              onChange={(e) => setThinkingLevel(e.target.value)}
              className={selectClass}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>

          <div>
            <label htmlFor="language" className={labelClass}>
              Language
            </label>
            <input
              id="language"
              type="text"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 inline-flex items-center rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {submitting ? "Provisioning..." : "Provision"}
        </button>
      </form>

      {/* Existing Boxes */}
      <div className="mt-10">
        <h2 className="text-lg font-semibold">Existing Instances</h2>

        {loading ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading...</p>
        ) : boxes.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            No instances found.
          </p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Customer</th>
                  <th className="pb-2 pr-4 font-medium">Namespace</th>
                  <th className="pb-2 pr-4 font-medium">Status</th>
                  <th className="pb-2 pr-4 font-medium">Model</th>
                  <th className="pb-2 pr-4 font-medium">Bundle</th>
                  <th className="pb-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {boxes.map((b) => (
                  <tr key={b.id} className="border-b">
                    <td className="py-3 pr-4 font-mono text-xs">
                      {b.customer_id}
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs">{b.k8s_namespace}</td>
                    <td className="py-3 pr-4">
                      <StatusBadge status={b.status} />
                    </td>
                    <td className="py-3 pr-4">{b.model}</td>
                    <td className="py-3 pr-4">{b.bundle_id ?? "-"}</td>
                    <td className="py-3">
                      <div className="flex gap-2">
                        {b.status === "active" && (
                          <button
                            onClick={() => handleAction(b.id, "suspend")}
                            disabled={actionLoading === `${b.id}-suspend`}
                            className="rounded bg-amber-600 px-2 py-1 text-xs text-white hover:bg-amber-700 disabled:opacity-50"
                          >
                            Suspend
                          </button>
                        )}
                        {b.status === "suspended" && (
                          <button
                            onClick={() => handleAction(b.id, "reactivate")}
                            disabled={
                              actionLoading === `${b.id}-reactivate`
                            }
                            className="rounded bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-700 disabled:opacity-50"
                          >
                            Reactivate
                          </button>
                        )}
                        {b.status !== "destroyed" && (
                          <button
                            onClick={() => handleAction(b.id, "destroy")}
                            disabled={actionLoading === `${b.id}-destroy`}
                            className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50"
                          >
                            Destroy
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
