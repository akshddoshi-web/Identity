import AsyncStorage from "@react-native-async-storage/async-storage";

/**
 * Points at the web app's origin (which hosts both the Next.js pages and
 * the tRPC/mobile-auth API routes) — set EXPO_PUBLIC_API_URL in apps/mobile/.env
 * to your machine's LAN IP when testing on a physical device, since
 * "localhost" from the device means the device itself, not your computer.
 */
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:3000";

const TOKEN_KEY = "identity.mobileToken";

export async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function setToken(token: string): Promise<void> {
  await AsyncStorage.setItem(TOKEN_KEY, token);
}

export async function clearToken(): Promise<void> {
  await AsyncStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_URL}/api/mobile-auth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error ?? "Login failed");
  await setToken(data.token);
  return data.user as { id: string; email: string; name: string | null };
}

export async function signup(email: string, password: string, name?: string) {
  await trpcCall("auth.signup", { email, password, name }, { auth: false });
  return login(email, password);
}

/**
 * Minimal tRPC-over-HTTP client (no @trpc/client dependency on mobile — a
 * plain fetch keeps the native bundle simpler). Matches the same
 * `{ result: { data } }` / `{ error }` envelope the web app's tRPC fetch
 * adapter returns, since both hit the same appRouter.
 */
export async function trpcCall<T = unknown>(
  procedure: string,
  input: unknown,
  options: { auth?: boolean; mutation?: boolean } = {},
): Promise<T> {
  const { auth = true, mutation = false } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (auth) {
    const token = await getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const url = mutation
    ? `${API_URL}/api/trpc/${procedure}`
    : `${API_URL}/api/trpc/${procedure}?input=${encodeURIComponent(JSON.stringify({ json: input }))}`;

  const res = await fetch(url, {
    method: mutation ? "POST" : "GET",
    headers,
    body: mutation ? JSON.stringify({ json: input }) : undefined,
  });

  const body = await res.json();
  if (!res.ok || body.error) {
    throw new Error(body.error?.json?.message ?? `${procedure} failed`);
  }
  return body.result.data.json as T;
}
