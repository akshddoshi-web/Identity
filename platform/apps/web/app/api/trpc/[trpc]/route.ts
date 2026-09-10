import { fetchRequestHandler } from "@trpc/server/adapters/fetch";
import { getServerSession } from "next-auth";
import { appRouter, createContextShape, verifyMobileToken } from "@identity/api";
import { authOptions } from "@/lib/auth";

/**
 * Web clients authenticate via the NextAuth session cookie; mobile clients
 * (no cookies) send `Authorization: Bearer <token>` from the JWT issued by
 * /api/mobile-auth. Both resolve to the same userId-based context.
 */
async function resolveUserId(req: Request): Promise<string | null> {
  const authHeader = req.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) {
    const payload = verifyMobileToken(authHeader.slice("Bearer ".length));
    return payload?.sub ?? null;
  }

  const session = await getServerSession(authOptions);
  return (session?.user as { id?: string } | undefined)?.id ?? null;
}

const handler = (req: Request) =>
  fetchRequestHandler({
    endpoint: "/api/trpc",
    req,
    router: appRouter,
    createContext: async () => createContextShape(await resolveUserId(req)),
  });

export { handler as GET, handler as POST };
