import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ClerkProvider, useAuth as useClerkAuthHook, useUser as useClerkUserHook } from "@clerk/expo";
import type { TokenCache } from "@clerk/expo";
import { storage } from "../lib/storage";

export const CLERK_PUBLISHABLE_KEY = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY;
export const isClerkConfigured = Boolean(CLERK_PUBLISHABLE_KEY);

/**
 * The shape every screen consumes, regardless of whether Clerk is configured.
 * In dev mode (no Clerk keys set yet) `signInLocal` lets the sign-in screen
 * simulate a session by storing an email/name pair in SecureStore, and the API
 * accepts it via the X-Dev-User-* headers its own ClerkAuthGuard falls back to.
 * This keeps the app demoable end-to-end before a Clerk project exists.
 */
export interface IdentityAuthState {
  isLoaded: boolean;
  isSignedIn: boolean;
  displayName: string | null;
  email: string | null;
  authHeaders: () => Promise<Record<string, string>>;
  signOut: () => Promise<void>;
  /** Only present in dev mode */
  signInLocal?: (email: string, name: string) => Promise<void>;
}

const AuthContext = createContext<IdentityAuthState | null>(null);

export function useIdentityAuth(): IdentityAuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useIdentityAuth must be used within IdentityAuthProvider");
  return ctx;
}

const DEV_USER_KEY = "identity.devUser";

function DevAuthProvider({ children }: { children: ReactNode }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const [user, setUser] = useState<{ email: string; name: string } | null>(null);

  useEffect(() => {
    storage
      .getItem(DEV_USER_KEY)
      .then((raw) => {
        if (raw) setUser(JSON.parse(raw));
      })
      .finally(() => setIsLoaded(true));
  }, []);

  const value = useMemo<IdentityAuthState>(
    () => ({
      isLoaded,
      isSignedIn: !!user,
      displayName: user?.name ?? null,
      email: user?.email ?? null,
      authHeaders: async (): Promise<Record<string, string>> =>
        user ? { "X-Dev-User-Email": user.email, "X-Dev-User-Name": user.name } : {},
      signOut: async () => {
        await storage.removeItem(DEV_USER_KEY);
        setUser(null);
      },
      signInLocal: async (email: string, name: string) => {
        const next = { email, name };
        await storage.setItem(DEV_USER_KEY, JSON.stringify(next));
        setUser(next);
      },
    }),
    [isLoaded, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function ClerkBridgeProvider({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useClerkAuthHook();
  const { user } = useClerkUserHook();

  const value = useMemo<IdentityAuthState>(
    () => ({
      isLoaded,
      isSignedIn: !!isSignedIn,
      displayName: user?.fullName ?? null,
      email: user?.primaryEmailAddress?.emailAddress ?? null,
      authHeaders: async (): Promise<Record<string, string>> => {
        const token = await getToken();
        return token ? { Authorization: `Bearer ${token}` } : {};
      },
      signOut: async () => {
        await signOut();
      },
    }),
    [isLoaded, isSignedIn, user, getToken, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

const tokenCache: TokenCache = {
  getToken: (key) => storage.getItem(key),
  saveToken: (key, token) => storage.setItem(key, token),
  clearToken: (key) => storage.removeItem(key),
};

export function IdentityAuthProvider({ children }: { children: ReactNode }) {
  if (isClerkConfigured) {
    return (
      <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY!} tokenCache={tokenCache}>
        <ClerkBridgeProvider>{children}</ClerkBridgeProvider>
      </ClerkProvider>
    );
  }
  return <DevAuthProvider>{children}</DevAuthProvider>;
}
