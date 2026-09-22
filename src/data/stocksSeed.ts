import { generateOHLCSeries } from "@/lib/ohlc";
import type { Stock, StocksData } from "@/types/stocks";

// Reference "today" for the generated OHLC series — matches the dates
// already used in the Home tab's seed data (Sep 2026).
const TODAY = "2026-09-22";
const TRADING_DAYS = 252; // ~1 year

interface RawStock extends Omit<Stock, "history"> {
  recentCloses: number[];
}

// Every field here (ticker, name, price, chg, held, shares, cost, sector,
// mktCap, pe, vol, avgVol, dayRange, wk52, news) mirrors the prototype's
// `stocks` array exactly. `recentCloses` is the prototype's original
// 10-point `history` array, pinned as the tail of the generated OHLC
// series. `tone` and `note` are intentionally NOT seeded here — they're
// computed by src/lib/stockInsights.ts from real numbers (concentration,
// day-range volatility, sector coverage), not hand-authored strings.
const RAW_STOCKS: RawStock[] = [
  {
    ticker: "NVDA",
    name: "NVIDIA Corp",
    price: 187.42,
    chg: 2.31,
    held: true,
    shares: 12,
    cost: 158.1,
    sector: "Technology",
    recentCloses: [142, 151, 149, 163, 171, 168, 180, 175, 183, 187],
    mktCap: "$4.61T",
    pe: "48.2",
    vol: "212.4M",
    avgVol: "198.1M",
    dayRange: "183.90 – 188.60",
    wk52: "98.10 – 195.20",
    news: [
      { headline: "NVIDIA supply partners raise 2027 capacity guidance", source: "Reuters", age: "3h" },
      { headline: "Analysts split on datacenter demand into next fiscal year", source: "Bloomberg", age: "1d" },
    ],
  },
  {
    ticker: "AAPL",
    name: "Apple Inc",
    price: 241.1,
    chg: -0.62,
    held: true,
    shares: 6,
    cost: 229.4,
    sector: "Technology",
    recentCloses: [233, 236, 240, 238, 242, 239, 244, 241, 243, 241],
    mktCap: "$3.68T",
    pe: "31.6",
    vol: "44.8M",
    avgVol: "51.2M",
    dayRange: "239.80 – 242.90",
    wk52: "196.40 – 248.10",
    news: [
      { headline: "Services revenue hits new quarterly record", source: "CNBC", age: "6h" },
      { headline: "Supply chain checks point to steady holiday demand", source: "AppleInsider", age: "2d" },
    ],
  },
  {
    ticker: "VTI",
    name: "Vanguard Total Market ETF",
    price: 289.6,
    chg: 0.44,
    held: true,
    shares: 4,
    cost: 270.0,
    sector: "Broad Market",
    recentCloses: [271, 274, 278, 276, 281, 284, 282, 286, 288, 290],
    mktCap: "—",
    pe: "—",
    vol: "3.1M",
    avgVol: "3.4M",
    dayRange: "288.10 – 290.40",
    wk52: "238.60 – 292.00",
    news: [{ headline: "Total-market funds see steady inflows this quarter", source: "Morningstar", age: "1d" }],
  },
  {
    ticker: "SCHD",
    name: "Schwab Dividend ETF",
    price: 29.87,
    chg: 0.14,
    held: false,
    sector: "Dividend/Income",
    recentCloses: [28.4, 28.6, 28.9, 29.1, 29.0, 29.3, 29.5, 29.6, 29.8, 29.87],
    mktCap: "—",
    pe: "—",
    vol: "8.7M",
    avgVol: "9.9M",
    dayRange: "29.70 – 29.95",
    wk52: "25.80 – 30.40",
    news: [{ headline: "Dividend ETF yields tick up amid rate uncertainty", source: "Yahoo Finance", age: "9h" }],
  },
  {
    ticker: "COIN",
    name: "Coinbase Global",
    price: 312.55,
    chg: -4.87,
    held: false,
    sector: "Financial/Crypto",
    recentCloses: [340, 335, 352, 330, 318, 325, 310, 298, 315, 312],
    mktCap: "$78.9B",
    pe: "—",
    vol: "9.4M",
    avgVol: "7.1M",
    dayRange: "305.10 – 320.40",
    wk52: "142.30 – 398.90",
    news: [
      { headline: "Crypto markets whipsaw on regulatory headlines", source: "CoinDesk", age: "4h" },
      { headline: "Coinbase expands institutional custody offering", source: "The Block", age: "3d" },
    ],
  },
];

const stocks: Stock[] = RAW_STOCKS.map(({ recentCloses, ...rest }) => ({
  ...rest,
  history: generateOHLCSeries(rest.ticker, TRADING_DAYS, recentCloses, TODAY),
}));

export const stocksSeed: StocksData = { stocks };
