import type { DashboardResponse, IdentityThread, OnboardingInput } from "@identity/shared";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:3000";

async function request<T>(path: string, headers: Record<string, string>, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...headers,
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getDashboard: (authHeaders: Record<string, string>) =>
    request<DashboardResponse>("/identity/dashboard", authHeaders),

  completeOnboarding: (authHeaders: Record<string, string>, body: OnboardingInput) =>
    request<{ threads: IdentityThread[] }>("/identity/onboarding", authHeaders, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
