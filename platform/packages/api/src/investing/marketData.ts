import type { StockFactors } from "@identity/shared";

/**
 * Alpha Vantage is the default provider — it has a usable free dev-tier key
 * (5 req/min, 25 req/day as of writing) which is enough to compute factors
 * for a small local dev universe. To swap providers (Polygon.io, IEX
 * Cloud) for production volume, replace the two fetch functions below;
 * the rest of the screener only depends on the `StockFactors` shape.
 */
const ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query";

function requireApiKey(): string {
  const key = process.env.MARKET_DATA_API_KEY;
  if (!key) throw new Error("MARKET_DATA_API_KEY env var is not set");
  return key;
}

interface AlphaVantageOverview {
  Symbol?: string;
  Sector?: string;
  PERatio?: string;
  PriceToBookRatio?: string;
  QuarterlyRevenueGrowthYOY?: string;
  ProfitMargin?: string;
  DebtToEquity?: string;
}

interface AlphaVantageDailySeries {
  "Time Series (Daily)"?: Record<string, { "4. close": string; "5. volume": string }>;
}

function toNumberOrNull(value: string | undefined): number | null {
  if (value === undefined || value === "" || value === "None") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

async function fetchOverview(symbol: string): Promise<AlphaVantageOverview> {
  const url = `${ALPHA_VANTAGE_BASE_URL}?function=OVERVIEW&symbol=${symbol}&apikey=${requireApiKey()}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Alpha Vantage OVERVIEW failed for ${symbol}: ${res.status}`);
  return (await res.json()) as AlphaVantageOverview;
}

async function fetchDailySeries(symbol: string): Promise<AlphaVantageDailySeries> {
  const url = `${ALPHA_VANTAGE_BASE_URL}?function=TIME_SERIES_DAILY&symbol=${symbol}&outputsize=full&apikey=${requireApiKey()}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Alpha Vantage TIME_SERIES_DAILY failed for ${symbol}: ${res.status}`);
  return (await res.json()) as AlphaVantageDailySeries;
}

export function tradingDaysAgoReturn(
  closesNewestFirst: number[],
  tradingDays: number,
): number | null {
  if (closesNewestFirst.length <= tradingDays) return null;
  const latest = closesNewestFirst[0];
  const past = closesNewestFirst[tradingDays];
  if (!latest || !past) return null;
  return latest / past - 1;
}

export function annualizedVolatility(closesNewestFirst: number[]): number | null {
  if (closesNewestFirst.length < 30) return null;
  const dailyReturns: number[] = [];
  for (let i = 0; i < closesNewestFirst.length - 1; i++) {
    dailyReturns.push(closesNewestFirst[i] / closesNewestFirst[i + 1] - 1);
  }
  const mean = dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length;
  const variance =
    dailyReturns.reduce((sum, r) => sum + (r - mean) ** 2, 0) / (dailyReturns.length - 1);
  return Math.sqrt(variance) * Math.sqrt(252);
}

export function volumeTrend(volumesNewestFirst: number[]): number | null {
  if (volumesNewestFirst.length < 60) return null;
  const recent20 = volumesNewestFirst.slice(0, 20);
  const trailing60 = volumesNewestFirst.slice(0, 60);
  const avg = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length;
  const longRunAvg = avg(trailing60);
  if (longRunAvg === 0) return null;
  return avg(recent20) / longRunAvg;
}

/** Fetches and derives all screener factors for one ticker from Alpha Vantage. */
export async function fetchStockFactors(symbol: string): Promise<StockFactors> {
  const [overview, series] = await Promise.all([fetchOverview(symbol), fetchDailySeries(symbol)]);

  const dailyPoints = Object.entries(series["Time Series (Daily)"] ?? {}).sort(
    ([dateA], [dateB]) => (dateA < dateB ? 1 : -1),
  );
  const closes = dailyPoints.map(([, v]) => Number(v["4. close"]));
  const volumes = dailyPoints.map(([, v]) => Number(v["5. volume"]));

  return {
    symbol: overview.Symbol ?? symbol,
    sector: overview.Sector ?? "Unknown",
    peRatio: toNumberOrNull(overview.PERatio),
    pbRatio: toNumberOrNull(overview.PriceToBookRatio),
    momentum3m: tradingDaysAgoReturn(closes, 63),
    momentum6m: tradingDaysAgoReturn(closes, 126),
    momentum12m: tradingDaysAgoReturn(closes, 252),
    volatility: annualizedVolatility(closes),
    volumeTrend: volumeTrend(volumes),
    revenueGrowth: toNumberOrNull(overview.QuarterlyRevenueGrowthYOY),
    netMargin: toNumberOrNull(overview.ProfitMargin),
    debtToEquity: toNumberOrNull(overview.DebtToEquity),
  };
}

/**
 * Default local/dev screener universe. "Analyze the entire market" (the
 * full S&P 500 or beyond) needs a paid, high-volume data feed and would
 * blow through Alpha Vantage's free-tier rate limit in minutes — this
 * fixed, small universe keeps local dev usable. Swap for a full S&P 500
 * constituent list (refreshed from a data provider) in production.
 */
export const DEV_SCREENER_UNIVERSE = [
  "AAPL",
  "MSFT",
  "GOOGL",
  "AMZN",
  "NVDA",
  "META",
  "JPM",
  "JNJ",
  "XOM",
  "PG",
] as const;
