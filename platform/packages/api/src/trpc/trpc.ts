import { initTRPC, TRPCError } from "@trpc/server";
import superjson from "superjson";
import { prisma } from "../db";

export interface Context {
  userId: string | null;
  prisma: typeof prisma;
}

export function createContextShape(userId: string | null): Context {
  return { userId, prisma };
}

const t = initTRPC.context<Context>().create({ transformer: superjson });

export const router = t.router;
export const publicProcedure = t.procedure;

export const protectedProcedure = t.procedure.use(({ ctx, next }) => {
  if (!ctx.userId) {
    throw new TRPCError({ code: "UNAUTHORIZED", message: "Sign in required" });
  }
  return next({ ctx: { ...ctx, userId: ctx.userId } });
});
