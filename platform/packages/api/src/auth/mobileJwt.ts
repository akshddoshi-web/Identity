import jwt from "jsonwebtoken";

/**
 * Mobile clients can't use NextAuth's cookie-based session, so they
 * exchange credentials once (via the web app's /api/mobile-auth route)
 * for a signed JWT and send it as `Authorization: Bearer <token>` on every
 * request after that — the same NEXTAUTH_SECRET signs both this token and
 * the web session cookie's JWT, so it's one shared session mechanism
 * across both clients, per spec.
 */
const MOBILE_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30; // 30 days

export interface MobileTokenPayload {
  sub: string;
  email: string;
}

function requireSecret(): string {
  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) throw new Error("NEXTAUTH_SECRET env var is not set");
  return secret;
}

export function signMobileToken(payload: MobileTokenPayload): string {
  return jwt.sign(payload, requireSecret(), { expiresIn: MOBILE_TOKEN_TTL_SECONDS });
}

export function verifyMobileToken(token: string): MobileTokenPayload | null {
  try {
    const decoded = jwt.verify(token, requireSecret());
    if (typeof decoded === "string" || !decoded.sub) return null;
    return { sub: decoded.sub, email: (decoded as { email: string }).email };
  } catch {
    return null;
  }
}
