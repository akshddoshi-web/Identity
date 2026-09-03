/** Identity of the caller once resolved from a Clerk session (or dev-mode header) */
export interface AuthenticatedUser {
  clerkUserId: string;
  email: string;
  name: string | null;
}
