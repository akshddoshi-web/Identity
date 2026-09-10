import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { hashPassword } from "../../auth/password";
import { checkRateLimit } from "../../auth/rateLimit";
import { publicProcedure, router } from "../trpc";

export const authRouter = router({
  signup: publicProcedure
    .input(
      z.object({
        email: z.string().email(),
        password: z.string().min(8, "Password must be at least 8 characters"),
        name: z.string().min(1).optional(),
      }),
    )
    .mutation(async ({ ctx, input }) => {
      const rateLimit = checkRateLimit(`signup:${input.email.toLowerCase()}`);
      if (!rateLimit.allowed) {
        throw new TRPCError({ code: "TOO_MANY_REQUESTS", message: "Too many attempts, try again shortly" });
      }

      const existing = await ctx.prisma.user.findUnique({ where: { email: input.email } });
      if (existing) {
        throw new TRPCError({ code: "CONFLICT", message: "An account with this email already exists" });
      }

      const hashedPassword = await hashPassword(input.password);
      const user = await ctx.prisma.user.create({
        data: { email: input.email, hashedPassword, name: input.name },
      });

      return { id: user.id, email: user.email, name: user.name };
    }),

  me: publicProcedure.query(async ({ ctx }) => {
    if (!ctx.userId) return null;
    return ctx.prisma.user.findUnique({
      where: { id: ctx.userId },
      select: { id: true, email: true, name: true, image: true },
    });
  }),
});
