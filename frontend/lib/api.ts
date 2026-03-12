import { supabase } from "./supabase";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  const res = await fetch(`${BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "Authorization": `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error" }));
    throw new Error(err.error ?? `HTTP ${res.status}`);
  }

  return res.json();
}

// Typed endpoint helpers
export const api = {
  complaints: {
    submit:       (body: any)         => apiFetch<any>("/complaints", { method: "POST", body: JSON.stringify(body) }),
    get:          (id: string)                           => apiFetch<any>(`/complaints/${id}`),
    list:         (params?: any)         => apiFetch<any>(`/complaints?${toQS(params)}`),
    updateStatus: (id: string, body: any)  => apiFetch<any>(`/complaints/${id}/status`, { method: "PATCH", body: JSON.stringify(body) }),
    getUploadUrl: ()                                     => apiFetch<any>("/complaints/upload-url", { method: "POST" }),
  },
  officers: {
    stats: (id: string) => apiFetch<any>(`/officers/${id}/stats`),
  },
  contractors: {
    scorecard:    (id: string)                      => apiFetch<any>(`/contractors/${id}/scorecard`),
    updateStatus: (id: string, body: { is_active: boolean; reason: string }) =>
                  apiFetch<any>(`/contractors/${id}/status`, { method: "PATCH", body: JSON.stringify(body) }),
  },
  analytics: {
    hotspots:        ()                          => apiFetch<any>("/analytics/hotspots"),
    slaCompliance:   (params?: any)  => apiFetch<any>(`/analytics/sla-compliance?${toQS(params)}`),
    complaintVolume: (params?: any)     => apiFetch<any>(`/analytics/complaint-volume?${toQS(params)}`),
    wardDensity:     (category?: string)         => apiFetch<any>(`/analytics/ward-density${category ? "?category=" + category : ""}`),
  },
  wards: {
    all: () => apiFetch<any>("/wards"),
  },
};

function toQS(params?: Record<string, unknown>): string {
  if (!params) return "";
  return new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)])
  ).toString();
}
