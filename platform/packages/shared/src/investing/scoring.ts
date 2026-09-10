/**
 * Factor-based screener scoring model. This is intentionally transparent
 * (a documented weighted-sum of z-scored factors) rather than a black box —
 * see README disclaimer: educational/informational only, not licensed
 * financial advice.
 */
export interface StockFactors {
  symbol: string;
  sector: string;
  /** Trailing P/E; lower is "cheaper" so this factor is inverted before scoring. */
  peRatio: number | null;
  /** Price/Book; lower is "cheaper", inverted before scoring. */
  pbRatio: number | null;
  /** Trailing price return over the window, as a fraction (0.12 = +12%). */
  momentum3m: number | null;
  momentum6m: number | null;
  momentum12m: number | null;
  /** Annualized volatility (stddev of daily returns), as a fraction. Lower is better, inverted. */
  volatility: number | null;
  /** Recent average volume vs. longer-run average volume, as a ratio (1.0 = flat). */
  volumeTrend: number | null;
  revenueGrowth: number | null;
  netMargin: number | null;
  /** Lower is better (less leveraged), inverted before scoring. */
  debtToEquity: number | null;
}

export interface FactorWeights {
  valuation: number;
  momentum: number;
  volatility: number;
  volumeTrend: number;
  fundamentals: number;
}

export const DEFAULT_FACTOR_WEIGHTS: FactorWeights = {
  valuation: 0.25,
  momentum: 0.3,
  volatility: 0.15,
  volumeTrend: 0.1,
  fundamentals: 0.2,
};

export interface ScoredStock {
  symbol: string;
  sector: string;
  compositeScore: number;
  subScores: {
    valuation: number | null;
    momentum: number | null;
    volatility: number | null;
    volumeTrend: number | null;
    fundamentals: number | null;
  };
}

function mean(values: number[]): number {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function stddev(values: number[], avg: number): number {
  if (values.length < 2) return 0;
  const variance = values.reduce((sum, v) => sum + (v - avg) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

/**
 * Z-scores a factor across the universe so different units (ratios,
 * percentages) become comparable. Missing values are excluded from the
 * mean/stddev calculation and left as null (a stock isn't penalized for
 * a data gap the provider didn't supply).
 */
function zScoreFactor(
  values: (number | null)[],
  { invert = false }: { invert?: boolean } = {},
): (number | null)[] {
  const present = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (present.length < 2) return values.map(() => null);

  const avg = mean(present);
  const sd = stddev(present, avg);
  if (sd === 0) return values.map((v) => (v === null ? null : 0));

  return values.map((v) => {
    if (v === null || !Number.isFinite(v)) return null;
    const z = (v - avg) / sd;
    return invert ? -z : z;
  });
}

function averageDefined(values: (number | null)[]): number | null {
  const present = values.filter((v): v is number => v !== null);
  if (present.length === 0) return null;
  return mean(present);
}

/**
 * Scores a universe of stocks (e.g. S&P 500 constituents) against each
 * other using cross-sectional z-scores per factor, combined into a
 * composite via configurable weights. Weights need not sum to 1; they're
 * normalized internally so callers can reason about relative emphasis.
 */
export function scoreStockUniverse(
  universe: StockFactors[],
  weights: FactorWeights = DEFAULT_FACTOR_WEIGHTS,
): ScoredStock[] {
  if (universe.length === 0) return [];

  const peZ = zScoreFactor(universe.map((s) => s.peRatio), { invert: true });
  const pbZ = zScoreFactor(universe.map((s) => s.pbRatio), { invert: true });
  const mom3Z = zScoreFactor(universe.map((s) => s.momentum3m));
  const mom6Z = zScoreFactor(universe.map((s) => s.momentum6m));
  const mom12Z = zScoreFactor(universe.map((s) => s.momentum12m));
  const volZ = zScoreFactor(universe.map((s) => s.volatility), { invert: true });
  const volumeZ = zScoreFactor(universe.map((s) => s.volumeTrend));
  const revGrowthZ = zScoreFactor(universe.map((s) => s.revenueGrowth));
  const marginZ = zScoreFactor(universe.map((s) => s.netMargin));
  const debtZ = zScoreFactor(universe.map((s) => s.debtToEquity), { invert: true });

  const totalWeight =
    weights.valuation + weights.momentum + weights.volatility + weights.volumeTrend +
    weights.fundamentals;

  return universe.map((stock, i) => {
    const valuation = averageDefined([peZ[i], pbZ[i]]);
    const momentum = averageDefined([mom3Z[i], mom6Z[i], mom12Z[i]]);
    const volatility = volZ[i];
    const volumeTrend = volumeZ[i];
    const fundamentals = averageDefined([revGrowthZ[i], marginZ[i], debtZ[i]]);

    const weightedSum =
      (valuation ?? 0) * weights.valuation +
      (momentum ?? 0) * weights.momentum +
      (volatility ?? 0) * weights.volatility +
      (volumeTrend ?? 0) * weights.volumeTrend +
      (fundamentals ?? 0) * weights.fundamentals;

    return {
      symbol: stock.symbol,
      sector: stock.sector,
      compositeScore: Number((weightedSum / totalWeight).toFixed(4)),
      subScores: { valuation, momentum, volatility, volumeTrend, fundamentals },
    };
  });
}

export function rankStocks(scored: ScoredStock[]): ScoredStock[] {
  return [...scored].sort((a, b) => b.compositeScore - a.compositeScore);
}

export function rankStocksBySector(scored: ScoredStock[]): Map<string, ScoredStock[]> {
  const bySector = new Map<string, ScoredStock[]>();
  for (const stock of scored) {
    if (!bySector.has(stock.sector)) bySector.set(stock.sector, []);
    bySector.get(stock.sector)!.push(stock);
  }
  for (const [sector, stocks] of bySector) {
    bySector.set(sector, rankStocks(stocks));
  }
  return bySector;
}
