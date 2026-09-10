/**
 * Standalone worker process for scheduled/background jobs. Not required
 * for `pnpm dev` — run separately with `pnpm --filter @identity/api worker`
 * once REDIS_URL is set, e.g. via `docker compose up redis`.
 */
import { Worker } from "bullmq";
import IORedis from "ioredis";
import { prisma } from "../db";
import { DEV_SCREENER_UNIVERSE, fetchStockFactors } from "../investing/marketData";
import { syncTransactionsForItem } from "../plaid/service";
import { JOB_NAMES } from "./queue";

const redisUrl = process.env.REDIS_URL;
if (!redisUrl) {
  console.error("REDIS_URL is not set; the worker has nothing to connect to. Exiting.");
  process.exit(1);
}
const connection = new IORedis(redisUrl, { maxRetriesPerRequest: null });

new Worker(
  JOB_NAMES.REFRESH_MARKET_DATA,
  async () => {
    const asOfDate = new Date();
    asOfDate.setHours(0, 0, 0, 0);
    for (const symbol of DEV_SCREENER_UNIVERSE) {
      const { symbol: _symbol, sector, ...rest } = await fetchStockFactors(symbol);
      await prisma.stockFactorSnapshot.upsert({
        where: { symbol_asOfDate: { symbol, asOfDate } },
        create: { symbol, asOfDate, sector, ...rest },
        update: { sector, ...rest },
      });
    }
  },
  { connection },
);

new Worker(
  JOB_NAMES.RESYNC_PLAID_TRANSACTIONS,
  async () => {
    const items = await prisma.plaidItem.findMany();
    for (const item of items) {
      await syncTransactionsForItem(item.id);
    }
  },
  { connection },
);

console.log("Worker listening for jobs:", Object.values(JOB_NAMES).join(", "));
