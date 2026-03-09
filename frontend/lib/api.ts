const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "API 오류가 발생했습니다.");
  }

  if (res.status === 204) return {} as T;
  return res.json();
}

// Auth
export const auth = {
  login: (email: string, password: string) =>
    request<{ tokens: { access: string; refresh: string } }>("/api/users/login/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  signup: (email: string, password: string) =>
    request("/api/users/signup/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () =>
    request("/api/users/logout/", { method: "POST" }),
};

// Inventory
export const inventory = {
  list: () => request<Inventory[]>("/api/inventories/"),
  sync: () =>
    request("/api/inventories/sync/", { method: "POST" }),
};

// Recommendations
export const recommendations = {
  audit: (inventory_id: number) =>
    request<Recommendation>("/api/recommendations/audit/", {
      method: "POST",
      body: JSON.stringify({ inventory_id }),
    }),
};

// Credentials
export const credentials = {
  list: () => request<Credential[]>("/api/users/credentials/"),
  create: (data: CredentialInput) =>
    request("/api/users/credentials/", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  test: (id: number) =>
    request(`/api/users/credentials/${id}/test/`, { method: "POST" }),
};

// Types
export interface Inventory {
  id: number;
  provider: string;
  resource_id: string;
  instance_type: string;
  region: string;
  region_normalized: string;
  vcpu: number;
  memory_gb: string;
  current_monthly_cost: string;
  cpu_usage_avg: string | null;
  cost_updated_at: string | null;
  is_active: boolean;
}

export interface Recommendation {
  recommendation_id: number;
  diagnosis: string;
  current: {
    provider: string;
    instance_type: string;
    monthly_cost: number;
  };
  recommended: {
    provider: string;
    instance_type: string;
    monthly_cost: number;
  };
  monthly_savings: number;
  reason: string;
  compare_result: CompareResult[];
}

export interface CompareResult {
  provider: string;
  instance_type: string;
  monthly_cost: number;
  region_normalized: string;
}

export interface Credential {
  id: number;
  provider: string;
  aws_default_region: string | null;
  is_active: boolean;
  created_at: string;
}

export interface CredentialInput {
  provider: string;
  credential_type: string;
  aws_access_key_id?: string;
  aws_secret_access_key?: string;
  aws_default_region?: string;
}
