// Rule-based "opinion" engine for Stocks, built on the same pattern as
// src/lib/accountability.ts: pure functions that take data and return a
// tone + reasoning, instead of tone/note strings baked into the seed data.
// Where a rule is a straightforward actual-vs-target ceiling check
// (position concentration), it reuses accountability's evaluateTarget()
// directly rather than reimplementing threshold logic.
import { evaluateTarget, type AlertTone } from "./accountability";
import type { Stock } from "@/types/stocks";

export type StockTone = AlertTone | "ok";

export interface StockInsight {
  ticker: string;
  tone: StockTone;
  title: string;
  note: string;
}

export interface StockRuleConfig {
  /** Single-position guideline as a fraction of held equity, e.g. 0.35 = 35%. */
  maxPositionPct: number;
  /** actual/target ratio beyond which a breach is a soft warning. */
  positionWarnRatio: number;
  /** actual/target ratio beyond which a breach escalates to a risk flag. */
  positionCritRatio: number;
  /** Day range as a fraction of price beyond which volatility is a soft warning. */
  dayRangeWarnPct: number;
  /** Day range as a fraction of price beyond which volatility is a risk flag. */
  dayRangeCritPct: number;
}

export const DEFAULT_STOCK_RULES: StockRuleConfig = {
  maxPositionPct: 0.35,
  positionWarnRatio: 1.0,
  positionCritRatio: 1.4,
  dayRangeWarnPct: 0.03,
  dayRangeCritPct: 0.045,
};

function parseDayRange(dayRange: string): [number, number] | null {
  const parts = dayRange.split(/[–-]/).map((s) => parseFloat(s.trim()));
  if (parts.length !== 2 || parts.some((n) => Number.isNaN(n))) return null;
  return [parts[0], parts[1]];
}

/** Day range width as a fraction of price — a real, computable volatility proxy. */
export function dayRangeVolatilityPct(stock: Stock): number | null {
  const range = parseDayRange(stock.dayRange);
  if (!range || stock.price === 0) return null;
  const [lo, hi] = range;
  return (hi - lo) / stock.price;
}

export function heldEquityValue(stocks: Stock[]): number {
  return stocks
    .filter((s) => s.held && s.shares)
    .reduce((sum, s) => sum + s.price * (s.shares ?? 0), 0);
}

function concentrationFlag(
  stock: Stock,
  portfolioValue: number,
  rules: StockRuleConfig,
): { tone: AlertTone; note: string } | null {
  if (!stock.held || !stock.shares || portfolioValue === 0) return null;

  const positionPct = (stock.price * stock.shares) / portfolioValue;
  const result = evaluateTarget(
    { id: stock.ticker, label: stock.ticker, actual: positionPct, target: rules.maxPositionPct, direction: "ceiling" },
    { critRatio: rules.positionCritRatio, warnRatio: rules.positionWarnRatio },
  );
  if (!result) return null;

  const pctS = Math.round(positionPct * 100);
  const guidelineS = Math.round(rules.maxPositionPct * 100);

  return {
    tone: result.tone,
    note:
      result.tone === "crit"
        ? `${stock.ticker} is ${pctS}% of your held equity — well past the ${guidelineS}% single-position guideline. This is a concentrated bet; a pullback here would hit your whole portfolio.`
        : `${stock.ticker} is ${pctS}% of your held equity — above the ${guidelineS}% single-position guideline you'd set. Worth trimming before adding more.`,
  };
}

function volatilityFlag(stock: Stock, rules: StockRuleConfig): { tone: AlertTone; note: string } | null {
  const dayRangePct = dayRangeVolatilityPct(stock);
  if (dayRangePct === null) return null;

  const result = evaluateTarget(
    { id: stock.ticker, label: stock.ticker, actual: dayRangePct, target: rules.dayRangeWarnPct, direction: "ceiling" },
    { critRatio: rules.dayRangeCritPct / rules.dayRangeWarnPct, warnRatio: 1.0 },
  );
  if (!result) return null;

  const pctS = (dayRangePct * 100).toFixed(1);

  return {
    tone: result.tone,
    note:
      result.tone === "crit"
        ? `${stock.ticker}'s day range is ${pctS}% of price — high volatility relative to a moderate risk tolerance. Flagged, not recommended.`
        : `${stock.ticker}'s day range is ${pctS}% of price — wider swings than the rest of your holdings. Worth checking against your risk tolerance.`,
  };
}

function diversificationFlag(stock: Stock, heldSectors: Set<string>): { tone: "ok"; note: string } | null {
  if (stock.held || heldSectors.has(stock.sector)) return null;
  return {
    tone: "ok",
    note: `Watchlist: fits a diversification gap in your portfolio — you have 0% ${stock.sector} exposure right now.`,
  };
}

const SEVERITY: Record<StockTone, number> = { crit: 2, warn: 1, ok: 0 };

/**
 * Evaluates every rule for every stock and returns one insight per ticker —
 * the highest-severity triggered rule wins, with a default "no flags" note
 * when nothing triggers. Mirrors accountability.ts's buildAvenueAlerts():
 * the engine decides tone, a small formatter attaches the copy.
 */
export function buildStockInsights(stocks: Stock[], rules: StockRuleConfig = DEFAULT_STOCK_RULES): StockInsight[] {
  const portfolioValue = heldEquityValue(stocks);
  const heldSectors = new Set(stocks.filter((s) => s.held).map((s) => s.sector));

  return stocks.map((stock) => {
    const candidates = [
      concentrationFlag(stock, portfolioValue, rules),
      volatilityFlag(stock, rules),
      diversificationFlag(stock, heldSectors),
    ].filter((c): c is { tone: StockTone; note: string } => c !== null);

    const winner = candidates.sort((a, b) => SEVERITY[b.tone] - SEVERITY[a.tone])[0];

    if (winner) {
      return { ticker: stock.ticker, tone: winner.tone, title: `${stock.ticker} — ${stock.name}`, note: winner.note };
    }

    return {
      ticker: stock.ticker,
      tone: "ok",
      title: `${stock.ticker} — ${stock.name}`,
      note: stock.held
        ? "No rule-based flags — position size and volatility are both inside target ranges."
        : "On the watchlist — no rule-based flags against your current holdings.",
    };
  });
}

export function insightForTicker(stocks: Stock[], ticker: string, rules?: StockRuleConfig): StockInsight | undefined {
  return buildStockInsights(stocks, rules).find((i) => i.ticker === ticker);
}
