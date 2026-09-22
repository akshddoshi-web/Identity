export interface OHLCPoint {
  date: string; // ISO yyyy-mm-dd
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface StockNewsItem {
  headline: string;
  source: string;
  age: string; // e.g. "3h", "1d"
}

export interface Stock {
  ticker: string;
  name: string;
  price: number;
  chg: number; // % change today
  held: boolean;
  shares?: number;
  cost?: number; // avg cost basis per share
  sector: string;
  /** ~1 trading year of daily OHLC bars, ending today. Both the line and the
   *  candlestick chart read from this same series. */
  history: OHLCPoint[];
  mktCap: string;
  pe: string;
  vol: string;
  avgVol: string;
  dayRange: string;
  wk52: string;
  news: StockNewsItem[];
}

export interface StocksData {
  stocks: Stock[];
}

export const CHART_RANGES = ["1D", "1W", "1M", "3M", "1Y", "ALL"] as const;
export type ChartRange = (typeof CHART_RANGES)[number];
