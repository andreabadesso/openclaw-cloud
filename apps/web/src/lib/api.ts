const API_URL = "/api";

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
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
}

export const api = {
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
};
