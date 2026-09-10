import type { ScoredStock } from "./scoring";

export interface RiskQuestionnaireInput {
  timeHorizonYears: number;
  /** Self-reported comfort with drawdowns, 1 (very conservative) - 5 (very aggressive). */
  drawdownComfort: number;
  /** Whether the user has other emergency savings outside this portfolio. */
  hasEmergencyFund: boolean;
}

/**
 * Maps the onboarding questionnaire to a 1-5 risk tolerance score. Simple,
 * documented, and adjustable — not a proprietary model. A longer horizon
 * and higher stated drawdown comfort both push tolerance up; no emergency
 * fund pulls it down (a market drop forces bad-timed withdrawals).
 */
export function scoreRiskTolerance(input: RiskQuestionnaireInput): number {
  let score = input.drawdownComfort;
  if (input.timeHorizonYears >= 10) score += 1;
  else if (input.timeHorizonYears <= 2) score -= 1;
  if (!input.hasEmergencyFund) score -= 1;
  return Math.min(5, Math.max(1, Math.round(score)));
}

export interface AllocationSuggestion {
  symbol: string;
  weightPercent: number;
}

/**
 * Simple, transparent allocation: takes the top N screened stocks, tilts
 * weight toward higher composite score, and scales concentration by risk
 * tolerance (higher tolerance = more concentrated in top picks; lower
 * tolerance = closer to equal-weight across a larger basket). This is a
 * basic risk-aware weighting scheme, not mean-variance optimization or
 * proprietary alpha generation — see in-app disclaimer.
 */
export function suggestAllocation(
  rankedStocks: ScoredStock[],
  riskTolerance: number,
  options: { maxPositions?: number } = {},
): AllocationSuggestion[] {
  if (rankedStocks.length === 0) return [];
  const clampedRisk = Math.min(5, Math.max(1, riskTolerance));
  const maxPositions = options.maxPositions ?? (clampedRisk <= 2 ? 15 : clampedRisk === 3 ? 10 : 6);

  const picks = rankedStocks.slice(0, Math.min(maxPositions, rankedStocks.length));

  // Shift scores to be non-negative, then raise to a power that grows with
  // risk tolerance so higher tolerance concentrates more into top scorers.
  const minScore = Math.min(...picks.map((s) => s.compositeScore));
  const shifted = picks.map((s) => s.compositeScore - minScore + 0.01);
  const concentrationExponent = 1 + (clampedRisk - 1) * 0.5; // 1.0 (risk 1) .. 3.0 (risk 5)
  const raised = shifted.map((s) => s ** concentrationExponent);
  const total = raised.reduce((a, b) => a + b, 0);

  return picks.map((stock, i) => ({
    symbol: stock.symbol,
    weightPercent: Number(((raised[i] / total) * 100).toFixed(2)),
  }));
}

export interface SimplifiedBacktestInput {
  allocation: AllocationSuggestion[];
  /** Trailing return over the backtest window per symbol, as a fraction (0.1 = +10%). */
  trailingReturnBySymbol: Record<string, number>;
}

export interface SimplifiedBacktestResult {
  weightedReturnPercent: number;
  /** Always surfaced alongside any backtest number — see in-app disclosure requirement. */
  disclaimer: string;
}

const BACKTEST_DISCLAIMER =
  "This is a simplified illustration using a single static allocation held over one trailing " +
  "period — not a full historical simulation with rebalancing, fees, taxes, or slippage. Past " +
  "performance (real or simulated) does not predict future results.";

/**
 * A deliberately simple backtest: applies the suggested weights to each
 * stock's trailing return over the same window and returns the blended
 * result. This is NOT a full historical equity-curve simulation (that
 * would need persisted daily price history + rebalancing logic) — flagged
 * as a stretch item beyond Tier 1 per the build plan, and disclosed as
 * such in the result itself so it's never presented without context.
 */
export function runSimplifiedBacktest(input: SimplifiedBacktestInput): SimplifiedBacktestResult {
  const weightedReturnPercent = input.allocation.reduce((sum, position) => {
    const trailingReturn = input.trailingReturnBySymbol[position.symbol] ?? 0;
    return sum + (position.weightPercent / 100) * trailingReturn * 100;
  }, 0);

  return { weightedReturnPercent: Number(weightedReturnPercent.toFixed(2)), disclaimer: BACKTEST_DISCLAIMER };
}
