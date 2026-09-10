import { z } from "zod";
import {
  computeNetWorthCents,
  createBudgetInputSchema,
  createPlannedExpenseInputSchema,
  detectRecurringTransactions,
  evaluateBudget,
} from "@identity/shared";
import { createLinkToken, exchangePublicTokenAndSync } from "../../plaid/service";
import { protectedProcedure, router } from "../trpc";

export const financeRouter = router({
  createPlaidLinkToken: protectedProcedure.mutation(async ({ ctx }) => {
    const linkToken = await createLinkToken(ctx.userId);
    return { linkToken };
  }),

  exchangePlaidPublicToken: protectedProcedure
    .input(z.object({ publicToken: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const item = await exchangePublicTokenAndSync(ctx.userId, input.publicToken);
      return { plaidItemId: item.plaidItemId };
    }),

  listAccounts: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.financialAccount.findMany({ where: { userId: ctx.userId } });
  }),

  netWorth: protectedProcedure.query(async ({ ctx }) => {
    const accounts = await ctx.prisma.financialAccount.findMany({ where: { userId: ctx.userId } });
    const assetAccountsCents = accounts.filter((a) => !a.isLiability).map((a) => a.currentBalanceCents);
    const liabilityAccountsCents = accounts.filter((a) => a.isLiability).map((a) => a.currentBalanceCents);
    return {
      netWorthCents: computeNetWorthCents({ assetAccountsCents, liabilityAccountsCents }),
      assetsCents: assetAccountsCents.reduce((a, b) => a + b, 0),
      liabilitiesCents: liabilityAccountsCents.reduce((a, b) => a + b, 0),
      asOf: new Date(),
    };
  }),

  listTransactions: protectedProcedure
    .input(
      z.object({
        accountId: z.string().optional(),
        category: z.string().optional(),
        from: z.coerce.date().optional(),
        to: z.coerce.date().optional(),
        limit: z.number().int().positive().max(500).default(100),
      }),
    )
    .query(async ({ ctx, input }) => {
      return ctx.prisma.transaction.findMany({
        where: {
          account: { userId: ctx.userId },
          accountId: input.accountId,
          category: input.category,
          postedAt: { gte: input.from, lte: input.to },
        },
        orderBy: { postedAt: "desc" },
        take: input.limit,
      });
    }),

  spendingByCategory: protectedProcedure
    .input(z.object({ from: z.coerce.date(), to: z.coerce.date() }))
    .query(async ({ ctx, input }) => {
      const transactions = await ctx.prisma.transaction.findMany({
        where: {
          account: { userId: ctx.userId },
          postedAt: { gte: input.from, lte: input.to },
          amountCents: { gt: 0 }, // Plaid convention: positive = money out
        },
      });
      const byCategory = new Map<string, number>();
      for (const tx of transactions) {
        byCategory.set(tx.category, (byCategory.get(tx.category) ?? 0) + tx.amountCents);
      }
      return Array.from(byCategory.entries()).map(([category, totalCents]) => ({
        category,
        totalCents,
      }));
    }),

  detectRecurring: protectedProcedure.query(async ({ ctx }) => {
    const transactions = await ctx.prisma.transaction.findMany({
      where: { account: { userId: ctx.userId } },
      orderBy: { postedAt: "asc" },
    });
    return detectRecurringTransactions(
      transactions.map((t) => ({ id: t.id, merchantName: t.merchantName, amountCents: t.amountCents, postedAt: t.postedAt })),
    );
  }),

  overrideTransactionCategory: protectedProcedure
    .input(z.object({ transactionId: z.string(), category: z.string().min(1) }))
    .mutation(async ({ ctx, input }) => {
      const transaction = await ctx.prisma.transaction.findFirstOrThrow({
        where: { id: input.transactionId, account: { userId: ctx.userId } },
      });
      return ctx.prisma.transaction.update({
        where: { id: transaction.id },
        data: { category: input.category, isUserOverridden: true },
      });
    }),

  addCategorizationRule: protectedProcedure
    .input(z.object({ pattern: z.string().min(1), category: z.string().min(1) }))
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.categorizationRule.create({
        data: { userId: ctx.userId, pattern: input.pattern, category: input.category },
      });
    }),

  listBudgets: protectedProcedure.query(async ({ ctx }) => {
    const budgets = await ctx.prisma.budget.findMany({ where: { userId: ctx.userId } });
    const withProgress = await Promise.all(
      budgets.map(async (budget) => {
        const spent = await ctx.prisma.transaction.aggregate({
          where: {
            account: { userId: ctx.userId },
            category: budget.category,
            postedAt: { gte: budget.periodStart, lte: budget.periodEnd },
            amountCents: { gt: 0 },
          },
          _sum: { amountCents: true },
        });
        const spentCents = spent._sum.amountCents ?? 0;
        return { ...budget, progress: evaluateBudget({ limitCents: budget.limitCents, spentCents }) };
      }),
    );
    return withProgress;
  }),

  createBudget: protectedProcedure.input(createBudgetInputSchema).mutation(async ({ ctx, input }) => {
    return ctx.prisma.budget.create({ data: { ...input, userId: ctx.userId } });
  }),

  deleteBudget: protectedProcedure.input(z.object({ id: z.string() })).mutation(async ({ ctx, input }) => {
    await ctx.prisma.budget.deleteMany({ where: { id: input.id, userId: ctx.userId } });
    return { ok: true };
  }),

  listPlannedExpenses: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.plannedExpense.findMany({
      where: { userId: ctx.userId },
      orderBy: { dueDate: "asc" },
      include: { reconciledTransaction: true },
    });
  }),

  createPlannedExpense: protectedProcedure
    .input(createPlannedExpenseInputSchema)
    .mutation(async ({ ctx, input }) => {
      return ctx.prisma.plannedExpense.create({ data: { ...input, userId: ctx.userId } });
    }),

  /**
   * Matches a planned expense to a real posted transaction: same rough
   * amount (+/-5%) and category, transaction not already reconciled.
   */
  reconcilePlannedExpense: protectedProcedure
    .input(z.object({ plannedExpenseId: z.string(), transactionId: z.string() }))
    .mutation(async ({ ctx, input }) => {
      const planned = await ctx.prisma.plannedExpense.findFirstOrThrow({
        where: { id: input.plannedExpenseId, userId: ctx.userId },
      });
      const transaction = await ctx.prisma.transaction.findFirstOrThrow({
        where: { id: input.transactionId, account: { userId: ctx.userId } },
      });
      return ctx.prisma.plannedExpense.update({
        where: { id: planned.id },
        data: { reconciledTransactionId: transaction.id },
      });
    }),

  suggestReconciliationMatches: protectedProcedure
    .input(z.object({ plannedExpenseId: z.string() }))
    .query(async ({ ctx, input }) => {
      const planned = await ctx.prisma.plannedExpense.findFirstOrThrow({
        where: { id: input.plannedExpenseId, userId: ctx.userId },
      });
      const candidates = await ctx.prisma.transaction.findMany({
        where: {
          account: { userId: ctx.userId },
          category: planned.category,
          plannedExpenses: { none: {} },
        },
      });
      const tolerance = Math.abs(planned.amountCents) * 0.05;
      return candidates.filter(
        (tx) => Math.abs(Math.abs(tx.amountCents) - Math.abs(planned.amountCents)) <= tolerance,
      );
    }),
});
