import type { User } from "./auth";

const API_URL = "/api";

const TOKEN_KEY = "openclaw_token";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = getToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      ...headers,
      ...options?.headers,
    },
    ...options,
  });

  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    window.location.reload();
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }

  return res.json();
}

export interface Box {
  id: string;
  customer_id: string;
  status: string;
  k8s_namespace: string;
  model: string;
  thinking_level: string;
  language: string;
  tier: string;
  niche: string | null;
  bundle_id: string | null;
  tokens_used: number;
  tokens_limit: number;
  telegram_user_ids: number[];
  created_at: string;
  activated_at: string | null;
}

export interface BundleProvider {
  provider: string;
  required: boolean;
}

export interface Bundle {
  id: string;
  slug: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  status: string;
  prompts: Record<string, string>;
  default_model: string;
  default_thinking_level: string;
  default_language: string;
  providers: BundleProvider[];
  mcp_servers: Record<string, unknown>;
  skills: string[];
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface BundleListItem {
  id: string;
  slug: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  providers: BundleProvider[];
  skills: string[];
  sort_order: number;
}

export interface ProvisionRequest {
  customer_email: string;
  telegram_bot_token: string;
  telegram_user_id: number;
  tier: "starter" | "pro" | "team";
  bundle_id: string;
  model?: string;
  thinking_level?: string;
  language?: string;
}

export interface Connection {
  id: string;
  provider: string;
  status: string;
  created_at: string | null;
}

export interface ConnectSession {
  session_token: string;
  connect_url: string;
}

export interface PodMetricsPoint {
  cpu_millicores: number;
  memory_bytes: number;
  ts: string;
}

export interface AnalyticsData {
  token_usage: {
    tokens_used: number;
    tokens_limit: number;
    period_start: string | null;
    period_end: string | null;
  };
  browser_sessions: {
    session_count: number;
    total_duration_ms: number;
  };
  pod_metrics_latest: PodMetricsPoint | null;
  pod_metrics_series: PodMetricsPoint[];
  tier: string;
}

export interface UpdateBoxRequest {
  model?: string;
  thinking_level?: string;
  language?: string;
  telegram_user_ids?: number[];
}

export const api = {
  getMe: (): Promise<User> => request<User>("/auth/me"),

  // Bundles
  getBundles: async (): Promise<BundleListItem[]> => {
    const data = await request<{ bundles: BundleListItem[] }>("/bundles");
    return data.bundles;
  },

  getBundle: (slug: string): Promise<Bundle> =>
    request<Bundle>(`/bundles/${slug}`),

  // Admin bundle CRUD
  getAdminBundles: (): Promise<Bundle[]> =>
    request<Bundle[]>("/internal/bundles"),

  createBundle: (data: Omit<Bundle, "id" | "created_at" | "updated_at">) =>
    request<Bundle>("/internal/bundles", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateBundle: (id: string, data: Partial<Bundle>) =>
    request<Bundle>(`/internal/bundles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  archiveBundle: (id: string) =>
    request(`/internal/bundles/${id}`, { method: "DELETE" }),

  setup: (data: Record<string, unknown>) =>
    request("/me/setup", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getBox: (id: string): Promise<Box> =>
    request<Box>(`/me/box`),

  getBoxes: async (): Promise<Box[]> => {
    const data = await request<{ boxes: Box[] }>("/internal/boxes");
    return data.boxes;
  },

  provision: (data: ProvisionRequest) =>
    request("/internal/provision", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  suspendBox: (id: string) =>
    request(`/internal/suspend/${id}`, { method: "POST" }),

  reactivateBox: (id: string) =>
    request(`/internal/reactivate/${id}`, { method: "POST" }),

  destroyBox: (id: string) =>
    request(`/internal/destroy/${id}`, { method: "POST" }),

  getConnections: async (): Promise<Connection[]> => {
    const data = await request<{ connections: Connection[] }>("/me/connections");
    return data.connections;
  },

  authorizeConnection: (provider: string) =>
    request<ConnectSession>(`/me/connections/${provider}/authorize`, {
      method: "POST",
    }),

  confirmConnection: (provider: string) =>
    request(`/me/connections/${provider}/confirm`, { method: "POST" }),

  deleteConnection: (id: string) =>
    request(`/me/connections/${id}`, { method: "DELETE" }),

  reconnectConnection: (id: string) =>
    request<ConnectSession>(`/me/connections/${id}/reconnect`, {
      method: "POST",
    }),

  getAnalytics: (hours = 24) =>
    request<AnalyticsData>(`/me/analytics?hours=${hours}`),

  updateBox: (data: UpdateBoxRequest) =>
    request<Box>("/me/box/update", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
