const API_URL = "/api";

// TODO: Replace with real JWT auth
const DEV_CUSTOMER_ID = "640a8328-dda2-4a48-a057-edfd93931667";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Customer-Id": DEV_CUSTOMER_ID,
      ...options?.headers,
    },
    ...options,
  });

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
  tokens_used: number;
  tokens_limit: number;
  telegram_user_ids: number[];
  created_at: string;
  activated_at: string | null;
}

export interface ProvisionRequest {
  customer_email: string;
  telegram_bot_token: string;
  telegram_user_id: number;
  tier: "starter" | "pro" | "team";
  model: string;
  thinking_level: string;
  language: string;
  niche?: string;
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

export const api = {
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
};
