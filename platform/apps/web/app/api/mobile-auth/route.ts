import { checkRateLimit, prisma, signMobileToken, verifyPassword } from "@identity/api";

/**
 * Mobile sign-in: exchanges email/password for a signed JWT (see
 * packages/api/src/auth/mobileJwt.ts) since the Expo app can't use
 * NextAuth's cookie-based session. The web app keeps using the normal
 * NextAuth credentials flow; both resolve to the same tRPC context shape.
 */
export async function POST(req: Request) {
  const body = (await req.json()) as { email?: string; password?: string };
  if (!body.email || !body.password) {
    return Response.json({ error: "email and password are required" }, { status: 400 });
  }

  const rateLimit = checkRateLimit(`mobile-login:${body.email.toLowerCase()}`);
  if (!rateLimit.allowed) {
    return Response.json({ error: "Too many attempts, try again shortly" }, { status: 429 });
  }

  const user = await prisma.user.findUnique({ where: { email: body.email } });
  if (!user?.hashedPassword) {
    return Response.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const valid = await verifyPassword(body.password, user.hashedPassword);
  if (!valid) {
    return Response.json({ error: "Invalid email or password" }, { status: 401 });
  }

  const token = signMobileToken({ sub: user.id, email: user.email });
  return Response.json({ token, user: { id: user.id, email: user.email, name: user.name } });
}
