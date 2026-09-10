import { z } from "zod";
import { DEFAULT_FACTOR_WEIGHTS, rankStocks, scoreStockUniverse, type StockFactors } from "@identity/shared";
import { DEV_SCREENER_UNIVERSE, fetchStockFactors } from "../../investing/marketData";
import { protectedProcedure, router } from "../trpc";

const factorWeightsSchema = z.object({
  valuation: z.number().min(0),
  momentum: z.number().min(0),
  volatility: z.number().min(0),
  volumeTrend: z.number().min(0),
  fundamentals: z.number().min(0),
});

export const investingRouter = router({
  /**
   * Refreshes factor snapshots from the market data provider for the dev
   * universe and stores them. Rate-limited providers (Alpha Vantage free
   * tier: 5 req/min) mean this should be triggered manually or by a
   * scheduled job, not on every screener page load — see `refreshCache`
   * vs. `screener` below.
   */
  refreshFactorCache: protectedProcedure.mutation(async ({ ctx }) => {
    const asOfDate = new Date();
    asOfDate.setHours(0, 0, 0, 0);
    const results: StockFactors[] = [];

    for (const symbol of DEV_SCREENER_UNIVERSE) {
      try {
        const factors = await fetchStockFactors(symbol);
        results.push(factors);
        await ctx.prisma.stockFactorSnapshot.upsert({
          where: { symbol_asOfDate: { symbol, asOfDate } },
          create: { symbol, asOfDate, sector: factors.sector, ...omitSymbolSector(factors) },
          update: { sector: factors.sector, ...omitSymbolSector(factors) },
        });
      } catch (err) {
        // A single symbol failing (rate limit, bad ticker) shouldn't abort the whole refresh.
        console.error(`Failed to refresh factors for ${symbol}`, err);
      }
    }

    return { refreshed: results.length, asOfDate };
  }),

  screener: protectedProcedure
    .input(z.object({ weights: factorWeightsSchema.optional(), sector: z.string().optional() }))
    .query(async ({ ctx, input }) => {
      const latestDate = await ctx.prisma.stockFactorSnapshot.findFirst({
        orderBy: { asOfDate: "desc" },
        select: { asOfDate: true },
      });
      if (!latestDate) return { asOfDate: null, ranked: [] };

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

      const scored = scoreStockUniverse(universe, input.weights ?? DEFAULT_FACTOR_WEIGHTS);
      const filtered = input.sector ? scored.filter((s) => s.sector === input.sector) : scored;

      return { asOfDate: latestDate.asOfDate, ranked: rankStocks(filtered) };
    }),

  defaultWeights: protectedProcedure.query(() => DEFAULT_FACTOR_WEIGHTS),
});

function omitSymbolSector(factors: StockFactors) {
  const { symbol: _symbol, sector: _sector, ...rest } = factors;
  return rest;
}
