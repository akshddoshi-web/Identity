import { z } from "zod";
import {
  DEFAULT_FACTOR_WEIGHTS,
  rankStocks,
  runSimplifiedBacktest,
  scoreRiskTolerance,
  scoreStockUniverse,
  suggestAllocation,
  type StockFactors,
} from "@identity/shared";
import { protectedProcedure, router } from "../trpc";

const questionnaireSchema = z.object({
  timeHorizonYears: z.number().int().positive(),
  drawdownComfort: z.number().int().min(1).max(5),
  hasEmergencyFund: z.boolean(),
  existingHoldingsNotes: z.string().optional(),
});

export const riskProfileRouter = router({
  submitQuestionnaire: protectedProcedure.input(questionnaireSchema).mutation(async ({ ctx, input }) => {
    const riskTolerance = scoreRiskTolerance(input);
    return ctx.prisma.riskProfile.upsert({
      where: { userId: ctx.userId },
      create: {
        userId: ctx.userId,
        timeHorizonYears: input.timeHorizonYears,
        riskTolerance,
        questionnaire: input,
      },
      update: { timeHorizonYears: input.timeHorizonYears, riskTolerance, questionnaire: input },
    });
  }),

  getProfile: protectedProcedure.query(async ({ ctx }) => {
    return ctx.prisma.riskProfile.findUnique({ where: { userId: ctx.userId } });
  }),

  /**
   * Tier 2: builds an allocation from the latest Tier 1 screener snapshot,
   * tilted by the user's risk profile, and a simplified illustrative
   * backtest disclosed with the same honesty requirement as the screener.
   */
  allocationSuggestion: protectedProcedure.query(async ({ ctx }) => {
    const riskProfile = await ctx.prisma.riskProfile.findUnique({ where: { userId: ctx.userId } });
    if (!riskProfile) {
      throw new Error("Complete the risk questionnaire first");
    }

    const latestDate = await ctx.prisma.stockFactorSnapshot.findFirst({
      orderBy: { asOfDate: "desc" },
      select: { asOfDate: true },
    });
    if (!latestDate) {
      return { allocation: [], backtest: null, asOfDate: null };
    }

    const snapshots = await ctx.prisma.stockFactorSnapshot.findMany({
      where: { asOfDate: latestDate.asOfDate },
    });
    const universe: StockFactors[] = snapshots.map((s) => ({
      symbol: s.symbol,
      sector: s.sector,
      peRatio: s.peRatio,
      pbRatio: s.pbRatio,
      momentum3m: s.momentum3m,
      momentum6m: s.momentum6m,
      momentum12m: s.momentum12m,
      volatility: s.volatility,
      volumeTrend: s.volumeTrend,
      revenueGrowth: s.revenueGrowth,
      netMargin: s.netMargin,
      debtToEquity: s.debtToEquity,
    }));

    const ranked = rankStocks(scoreStockUniverse(universe, DEFAULT_FACTOR_WEIGHTS));
    const allocation = suggestAllocation(ranked, riskProfile.riskTolerance);

    const trailingReturnBySymbol = Object.fromEntries(
      snapshots.map((s) => [s.symbol, s.momentum12m ?? 0]),
    );
    const backtest = runSimplifiedBacktest({ allocation, trailingReturnBySymbol });

    return { allocation, backtest, asOfDate: latestDate.asOfDate };
  }),
});
