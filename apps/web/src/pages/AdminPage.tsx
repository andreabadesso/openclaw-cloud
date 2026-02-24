import { useEffect, useState, type FormEvent } from "react";
import { StatusBadge } from "@/components/status-badge";
import { BundleCard } from "@/components/bundle-card";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { Box, Bundle } from "@/lib/api";
import { useRouter } from "@/i18n/navigation";
import { X, ExternalLink } from "lucide-react";

const IS_DEV = import.meta.env.VITE_DEV_MODE === "true";

export default function AdminPage() {
  const { isLoading: authLoading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!authLoading && !isAuthenticated && !IS_DEV) {
      router.replace("/login");
    }
  }, [authLoading, isAuthenticated, router]);
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const [customerEmail, setCustomerEmail] = useState("");
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [telegramUserId, setTelegramUserId] = useState("");
  const [tier, setTier] = useState<"starter" | "pro" | "team">("starter");
  const [selectedBundleId, setSelectedBundleId] = useState("");

  const [bundleTab, setBundleTab] = useState<"list" | "edit">("list");
  const [editingBundle, setEditingBundle] = useState<Partial<Bundle> | null>(null);
  const [bundleSubmitting, setBundleSubmitting] = useState(false);
  const [bundleMessage, setBundleMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const fetchData = () => {
    Promise.all([
      api.getBoxes().catch(() => []),
      api.getAdminBundles().catch(() => []),
    ])
      .then(([b, bndls]) => {
        setBoxes(b);
        setBundles(bndls);
        if (bndls.length > 0 && !selectedBundleId) {
          setSelectedBundleId(bndls[0].id);
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (authLoading || (!isAuthenticated && !IS_DEV)) return;
    fetchData();
  }, [authLoading, isAuthenticated]);

  if (authLoading) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-12">
        <div className="skeleton h-8 w-40" />
      </div>
    );
  }

  if (!isAuthenticated && !IS_DEV) return null;

  const handleProvision = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedBundleId) return;
    setSubmitting(true);
    setMessage(null);

    try {
      await api.provision({
        customer_email: customerEmail,
        telegram_bot_token: telegramBotToken,
        telegram_user_id: parseInt(telegramUserId, 10),
        tier,
        bundle_id: selectedBundleId,
      });
      setMessage({ type: "success", text: "Instance provisioned successfully." });
      setCustomerEmail("");
      setTelegramBotToken("");
      setTelegramUserId("");
      setTier("starter");
      fetchData();
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
      fetchData();
    } catch {
      alert(`Failed to ${action} box.`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleBundleSave = async (e: FormEvent) => {
    e.preventDefault();
    if (!editingBundle) return;
    setBundleSubmitting(true);
    setBundleMessage(null);

    try {
      let providers = [];
      try {
        providers = JSON.parse((editingBundle as any)._providersJson as string || "[]");
      } catch { providers = []; }

      let mcpServers = {};
      try {
        mcpServers = JSON.parse((editingBundle as any)._mcpServersJson as string || "{}");
      } catch { mcpServers = {}; }

      const payload = {
        slug: editingBundle.slug || "",
        name: editingBundle.name || "",
        description: editingBundle.description || "",
        icon: editingBundle.icon || "🤖",
        color: editingBundle.color || "#10B981",
        status: editingBundle.status || "draft",
        prompts: editingBundle.prompts || {},
        default_model: editingBundle.default_model || "claude-sonnet-4-20250514",
        default_thinking_level: editingBundle.default_thinking_level || "medium",
        default_language: editingBundle.default_language || "en",
        providers,
        mcp_servers: mcpServers,
        skills: editingBundle.skills || [],
        sort_order: editingBundle.sort_order || 0,
      };

      if (editingBundle.id) {
        await api.updateBundle(editingBundle.id, payload);
        setBundleMessage({ type: "success", text: "Bundle updated." });
      } else {
        await api.createBundle(payload as any);
        setBundleMessage({ type: "success", text: "Bundle created." });
      }
      fetchData();
      setBundleTab("list");
      setEditingBundle(null);
    } catch (err) {
      setBundleMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to save bundle.",
      });
    } finally {
      setBundleSubmitting(false);
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

      {/* Bundles Section */}
      <div className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Agent Bundles</h2>
          <button
            onClick={() => {
              setEditingBundle({
                slug: "",
                name: "",
                description: "",
                icon: "🤖",
                color: "#10B981",
                status: "draft",
                prompts: {},
                default_model: "claude-sonnet-4-20250514",
                default_thinking_level: "medium",
                default_language: "en",
                providers: [],
                mcp_servers: {},
                skills: [],
                sort_order: 0,
                _providersJson: "[]",
                _mcpServersJson: "{}",
              } as any);
              setBundleTab("edit");
              setBundleMessage(null);
            }}
            className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
          >
            + New Bundle
          </button>
        </div>

        {bundleTab === "list" && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Icon</th>
                  <th className="pb-2 pr-4 font-medium">Name</th>
                  <th className="pb-2 pr-4 font-medium">Slug</th>
                  <th className="pb-2 pr-4 font-medium">Status</th>
                  <th className="pb-2 pr-4 font-medium">Skills</th>
                  <th className="pb-2 pr-4 font-medium">Providers</th>
                  <th className="pb-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {bundles.map((b) => (
                  <tr
                    key={b.id}
                    className="border-b cursor-pointer transition-colors hover:bg-white/[0.02]"
                    onClick={() => {
                      setEditingBundle({
                        ...b,
                        _providersJson: JSON.stringify(b.providers, null, 2),
                        _mcpServersJson: JSON.stringify(b.mcp_servers, null, 2),
                      } as any);
                      setBundleTab("edit");
                      setBundleMessage(null);
                    }}
                  >
                    <td className="py-3 pr-4 text-xl">{b.icon}</td>
                    <td className="py-3 pr-4">{b.name}</td>
                    <td className="py-3 pr-4 font-mono text-xs">{b.slug}</td>
                    <td className="py-3 pr-4">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          b.status === "published"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : b.status === "draft"
                              ? "bg-amber-500/15 text-amber-400"
                              : "bg-white/5 text-white/40"
                        }`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-xs text-white/50">{b.skills.length}</td>
                    <td className="py-3 pr-4 text-xs text-white/50">{b.providers.length}</td>
                    <td className="py-3">
                      <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => {
                            setEditingBundle({
                              ...b,
                              _providersJson: JSON.stringify(b.providers, null, 2),
                              _mcpServersJson: JSON.stringify(b.mcp_servers, null, 2),
                            } as any);
                            setBundleTab("edit");
                            setBundleMessage(null);
                          }}
                          className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-700"
                        >
                          Edit
                        </button>
                        {b.status !== "archived" && (
                          <button
                            onClick={async () => {
                              if (!confirm("Archive this bundle?")) return;
                              await api.archiveBundle(b.id);
                              fetchData();
                            }}
                            className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700"
                          >
                            Archive
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

        {bundleTab === "edit" && editingBundle && (
          <form onSubmit={handleBundleSave} className="mt-4 rounded-lg border bg-card p-6">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="font-semibold">
                {editingBundle.id ? "Edit Bundle" : "New Bundle"}
              </h3>
              <button
                type="button"
                onClick={() => { setBundleTab("list"); setEditingBundle(null); }}
                className="text-xs text-white/40 hover:text-white/70"
              >
                Cancel
              </button>
            </div>

            {bundleMessage && (
              <div
                className={`mb-4 rounded-md p-3 text-sm ${
                  bundleMessage.type === "success"
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-red-500/15 text-red-400"
                }`}
              >
                {bundleMessage.text}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelClass}>Slug</label>
                <input
                  type="text"
                  required
                  value={editingBundle.slug || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, slug: e.target.value })}
                  className={inputClass}
                  disabled={!!editingBundle.id}
                />
              </div>
              <div>
                <label className={labelClass}>Name</label>
                <input
                  type="text"
                  required
                  value={editingBundle.name || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, name: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="sm:col-span-2">
                <label className={labelClass}>Description</label>
                <input
                  type="text"
                  value={editingBundle.description || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, description: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Icon</label>
                <input
                  type="text"
                  value={editingBundle.icon || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, icon: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Color</label>
                <input
                  type="text"
                  value={editingBundle.color || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, color: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Status</label>
                <select
                  value={editingBundle.status || "draft"}
                  onChange={(e) => setEditingBundle({ ...editingBundle, status: e.target.value })}
                  className={selectClass}
                >
                  <option value="draft">Draft</option>
                  <option value="published">Published</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Sort Order</label>
                <input
                  type="number"
                  value={editingBundle.sort_order || 0}
                  onChange={(e) => setEditingBundle({ ...editingBundle, sort_order: parseInt(e.target.value) || 0 })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Default Model</label>
                <input
                  type="text"
                  value={editingBundle.default_model || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, default_model: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass}>Default Thinking Level</label>
                <select
                  value={editingBundle.default_thinking_level || "medium"}
                  onChange={(e) => setEditingBundle({ ...editingBundle, default_thinking_level: e.target.value })}
                  className={selectClass}
                >
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Default Language</label>
                <input
                  type="text"
                  value={editingBundle.default_language || ""}
                  onChange={(e) => setEditingBundle({ ...editingBundle, default_language: e.target.value })}
                  className={inputClass}
                />
              </div>

              <div className="sm:col-span-2">
                <label className={labelClass}>Prompts (soul)</label>
                <textarea
                  rows={6}
                  value={editingBundle.prompts?.soul || ""}
                  onChange={(e) => setEditingBundle({
                    ...editingBundle,
                    prompts: { ...editingBundle.prompts, soul: e.target.value },
                  })}
                  placeholder="Main system prompt (written to CLAUDE.md)"
                  className={inputClass}
                />
              </div>
              <div className="sm:col-span-2">
                <label className={labelClass}>Prompts (rules)</label>
                <textarea
                  rows={4}
                  value={editingBundle.prompts?.rules || ""}
                  onChange={(e) => setEditingBundle({
                    ...editingBundle,
                    prompts: { ...editingBundle.prompts, rules: e.target.value },
                  })}
                  placeholder="Rules and behavioral guidelines (written to SOUL.md)"
                  className={inputClass}
                />
              </div>
              <div className="sm:col-span-2">
                <label className={labelClass}>Prompts (tools)</label>
                <textarea
                  rows={4}
                  value={editingBundle.prompts?.tools || ""}
                  onChange={(e) => setEditingBundle({
                    ...editingBundle,
                    prompts: { ...editingBundle.prompts, tools: e.target.value },
                  })}
                  placeholder="Tool usage instructions (written to TOOLS.md)"
                  className={inputClass}
                />
              </div>
              <div className="sm:col-span-2">
                <label className={labelClass}>Prompts (identity)</label>
                <textarea
                  rows={4}
                  value={editingBundle.prompts?.identity || ""}
                  onChange={(e) => setEditingBundle({
                    ...editingBundle,
                    prompts: { ...editingBundle.prompts, identity: e.target.value },
                  })}
                  placeholder="Identity reinforcement (written to IDENTITY.md)"
                  className={inputClass}
                />
              </div>

              <div className="sm:col-span-2">
                <label className={labelClass}>Providers (JSON)</label>
                <textarea
                  rows={3}
                  value={(editingBundle as any)._providersJson || "[]"}
                  onChange={(e) => setEditingBundle({ ...editingBundle, _providersJson: e.target.value } as any)}
                  placeholder='[{"provider": "google", "required": false}]'
                  className={`${inputClass} font-mono text-xs`}
                />
              </div>

              <div className="sm:col-span-2">
                <label className={labelClass}>MCP Servers (JSON)</label>
                <textarea
                  rows={3}
                  value={(editingBundle as any)._mcpServersJson || "{}"}
                  onChange={(e) => setEditingBundle({ ...editingBundle, _mcpServersJson: e.target.value } as any)}
                  placeholder='{"server_name": {"type": "http", "baseUrl": "..."}}'
                  className={`${inputClass} font-mono text-xs`}
                />
              </div>

              <div className="sm:col-span-2">
                <label className={labelClass}>Skills (ClawHub slugs)</label>
                <div className="flex flex-wrap gap-1.5 rounded-md border bg-background p-2 min-h-[42px]">
                  {(editingBundle.skills || []).map((slug, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 pl-2.5 pr-1 py-0.5 text-xs text-emerald-400"
                    >
                      {slug}
                      <a
                        href={`https://clawhub.ai/skills/${slug}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-400/50 hover:text-emerald-400 p-0.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="h-2.5 w-2.5" />
                      </a>
                      <button
                        type="button"
                        onClick={() => setEditingBundle({
                          ...editingBundle,
                          skills: (editingBundle.skills || []).filter((_, j) => j !== i),
                        })}
                        className="text-emerald-400/40 hover:text-red-400 p-0.5"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    placeholder={editingBundle.skills?.length ? "" : "Type slug and press Enter..."}
                    className="flex-1 min-w-[120px] bg-transparent text-sm outline-none text-white/80 placeholder:text-white/20"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === ",") {
                        e.preventDefault();
                        const val = (e.target as HTMLInputElement).value.trim().replace(/,$/, "");
                        if (val && !(editingBundle.skills || []).includes(val)) {
                          setEditingBundle({
                            ...editingBundle,
                            skills: [...(editingBundle.skills || []), val],
                          });
                        }
                        (e.target as HTMLInputElement).value = "";
                      }
                      if (e.key === "Backspace" && !(e.target as HTMLInputElement).value && editingBundle.skills?.length) {
                        setEditingBundle({
                          ...editingBundle,
                          skills: editingBundle.skills.slice(0, -1),
                        });
                      }
                    }}
                  />
                </div>
                <p className="mt-1 text-[11px] text-white/30">
                  Skill slugs from <a href="https://clawhub.ai" target="_blank" rel="noopener noreferrer" className="text-emerald-400/60 hover:text-emerald-400">clawhub.ai</a>. Press Enter or comma to add. Installed automatically when the pod boots.
                </p>
              </div>
            </div>

            {editingBundle.name && (
              <div className="mt-6 rounded-lg border border-dashed border-white/10 p-4">
                <p className="mb-3 text-xs font-medium text-white/30 uppercase tracking-wider">Card Preview</p>
                <div className="max-w-sm">
                  <BundleCard
                    bundle={{
                      id: editingBundle.id || "preview",
                      slug: editingBundle.slug || "preview",
                      name: editingBundle.name || "",
                      description: editingBundle.description || "",
                      icon: editingBundle.icon || "🤖",
                      color: editingBundle.color || "#10B981",
                      providers: (() => {
                        try { return JSON.parse((editingBundle as any)._providersJson || "[]"); }
                        catch { return []; }
                      })(),
                      skills: editingBundle.skills || [],
                      sort_order: editingBundle.sort_order || 0,
                    }}
                    ctaLabel="Get Started"
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={bundleSubmitting}
              className="mt-6 inline-flex items-center rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {bundleSubmitting ? "Saving..." : "Save Bundle"}
            </button>
          </form>
        )}
      </div>

      {/* Provision Form */}
      <form
        onSubmit={handleProvision}
        className="mt-10 rounded-lg border bg-card p-6"
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
            <label htmlFor="bundle" className={labelClass}>
              Agent Bundle
            </label>
            <select
              id="bundle"
              value={selectedBundleId}
              onChange={(e) => setSelectedBundleId(e.target.value)}
              className={selectClass}
            >
              {bundles.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.icon} {b.name} ({b.status})
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting || !selectedBundleId}
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
                {boxes.map((b) => {
                  const bundle = bundles.find((bndl) => bndl.id === b.bundle_id);
                  return (
                    <tr key={b.id} className="border-b">
                      <td className="py-3 pr-4 font-mono text-xs">
                        {b.customer_id}
                      </td>
                      <td className="py-3 pr-4 font-mono text-xs">{b.k8s_namespace}</td>
                      <td className="py-3 pr-4">
                        <StatusBadge status={b.status} />
                      </td>
                      <td className="py-3 pr-4">{b.model}</td>
                      <td className="py-3 pr-4">
                        {bundle ? `${bundle.icon} ${bundle.name}` : b.niche ?? "-"}
                      </td>
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
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
