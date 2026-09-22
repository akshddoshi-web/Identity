import type { ChartRange, OHLCPoint } from "@/types/stocks";

// Deterministic PRNG (mulberry32) so seed data is stable across reloads —
// no Math.random(), so the "randomly" generated lead-in history never
// changes between renders or after a hard refresh.
function mulberry32(seed: number) {
  let t = seed;
  return function () {
    t |= 0;
    t = (t + 0x6d2b79f5) | 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(h, 31) + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

/**
 * Builds a ~1-trading-year daily OHLC series for a ticker. The most recent
 * `recentCloses.length` closes are pinned to the prototype's original
 * `history` values (so the last ~10 days match index.html exactly); earlier
 * days are synthesized backward with a seeded random walk so every stock
 * gets a full, deterministic series that both the line chart and the
 * candlestick chart can slice by range.
 */
export function generateOHLCSeries(
  ticker: string,
  days: number,
  recentCloses: number[],
  endDateISO: string,
): OHLCPoint[] {
  const rand = mulberry32(hashString(ticker));
  const leadLen = Math.max(days - recentCloses.length, 0);

  const lead: number[] = [];
  let cursor = recentCloses[0];
  for (let i = 0; i < leadLen; i++) {
    const drift = (rand() - 0.5) * 0.03; // +/-1.5% daily wiggle
    cursor = Math.max(cursor / (1 + drift), 0.01);
    lead.unshift(cursor);
  }

  const closes = [...lead, ...recentCloses];
  const end = new Date(endDateISO + "T00:00:00");

  return closes.map((close, i) => {
    const date = new Date(end);
    date.setDate(date.getDate() - (closes.length - 1 - i));

    const open = i === 0 ? close * (1 - (rand() - 0.5) * 0.01) : closes[i - 1];
    const high = Math.max(open, close) * (1 + rand() * 0.012);
    const low = Math.min(open, close) * (1 - rand() * 0.012);

    return {
      date: date.toISOString().slice(0, 10),
      open: Number(open.toFixed(2)),
      high: Number(high.toFixed(2)),
      low: Number(low.toFixed(2)),
      close: Number(close.toFixed(2)),
    };
  });
}

const RANGE_DAYS: Record<ChartRange, number> = {
  // No true intraday data in this mock dataset — "1D" shows the last few
  // daily bars rather than a single point so the chart still reads.
  "1D": 5,
  "1W": 7,
  "1M": 22,
  "3M": 65,
  "1Y": 252,
  ALL: Infinity,
};

export function sliceRange(history: OHLCPoint[], range: ChartRange): OHLCPoint[] {
  const n = RANGE_DAYS[range];
  if (!Number.isFinite(n) || n >= history.length) return history;
  return history.slice(history.length - n);
}
