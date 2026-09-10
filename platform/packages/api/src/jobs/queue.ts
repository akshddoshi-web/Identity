import { Queue } from "bullmq";
import IORedis from "ioredis";

/**
 * Background jobs (nightly market data refresh, periodic transaction
 * re-sync) are optional for local dev: the web app boots and works fully
 * without Redis running. Only code paths that explicitly enqueue/run jobs
 * touch this module, so a missing REDIS_URL never blocks `pnpm dev`.
 */
let connection: IORedis | null = null;

function getConnection(): IORedis {
  if (!process.env.REDIS_URL) {
    throw new Error("REDIS_URL is not set — background jobs are disabled");
  }
  if (!connection) {
    connection = new IORedis(process.env.REDIS_URL, { maxRetriesPerRequest: null });
  }
  return connection;
}

export const JOB_NAMES = {
  REFRESH_MARKET_DATA: "refresh-market-data",
  RESYNC_PLAID_TRANSACTIONS: "resync-plaid-transactions",
} as const;

export function isJobQueueEnabled(): boolean {
  return Boolean(process.env.REDIS_URL);
}

export function getMarketDataQueue(): Queue {
  return new Queue(JOB_NAMES.REFRESH_MARKET_DATA, { connection: getConnection() });
}

export function getPlaidResyncQueue(): Queue {
  return new Queue(JOB_NAMES.RESYNC_PLAID_TRANSACTIONS, { connection: getConnection() });
}
