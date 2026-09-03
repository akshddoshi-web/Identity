import { CanActivate, ExecutionContext, Injectable, Logger, UnauthorizedException } from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { createClerkClient, verifyToken } from "@clerk/backend";
import type { AuthenticatedUser } from "./auth.types";

/**
 * Verifies the caller's Clerk session JWT and attaches an AuthenticatedUser to the request.
 *
 * When CLERK_SECRET_KEY is unset (local dev with no Clerk project configured yet), falls back
 * to trusting an `X-Dev-User-Email` / `X-Dev-User-Name` header pair instead of rejecting every
 * request outright. This keeps Phase 0 runnable end-to-end before real Clerk keys exist; it
 * must never be reachable when CLERK_SECRET_KEY is set in a real environment.
 */
@Injectable()
export class ClerkAuthGuard implements CanActivate {
  private readonly logger = new Logger(ClerkAuthGuard.name);

  constructor(private readonly config: ConfigService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const secretKey = this.config.get<string>("CLERK_SECRET_KEY");

    if (!secretKey) {
      const devUser = this.resolveDevUser(request);
      if (!devUser) {
        throw new UnauthorizedException(
          "No Clerk session and no X-Dev-User-Email header. In dev mode, pass X-Dev-User-Email to simulate a signed-in user.",
        );
      }
      request.user = devUser;
      return true;
    }

    const authHeader: string | undefined = request.headers["authorization"];
    const token = authHeader?.startsWith("Bearer ") ? authHeader.slice("Bearer ".length) : undefined;
    if (!token) {
      throw new UnauthorizedException("Missing Authorization: Bearer <token> header");
    }

    try {
      const claims = await verifyToken(token, { secretKey });
      const clerkClient = createClerkClient({ secretKey });
      const clerkUser = await clerkClient.users.getUser(claims.sub);
      const primaryEmail = clerkUser.emailAddresses.find(
        (e) => e.id === clerkUser.primaryEmailAddressId,
      )?.emailAddress;

      if (!primaryEmail) {
        throw new UnauthorizedException("Clerk user has no primary email address");
      }

      const user: AuthenticatedUser = {
        clerkUserId: clerkUser.id,
        email: primaryEmail,
        name: [clerkUser.firstName, clerkUser.lastName].filter(Boolean).join(" ") || null,
      };
      request.user = user;
      return true;
    } catch (err) {
      this.logger.warn(`Clerk token verification failed: ${(err as Error).message}`);
      throw new UnauthorizedException("Invalid or expired session");
    }
  }

  private resolveDevUser(request: any): AuthenticatedUser | null {
    const email = request.headers["x-dev-user-email"];
    if (!email || typeof email !== "string") return null;
    const name = typeof request.headers["x-dev-user-name"] === "string" ? request.headers["x-dev-user-name"] : null;
    return { clerkUserId: `dev_${email}`, email, name };
  }
}
