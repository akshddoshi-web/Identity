/**
 * Minimal in-memory rate limiter for auth endpoints (login, signup).
 * Fine for a single-instance dev/small deployment; swap for a Redis-backed
 * limiter (we already depend on ioredis for BullMQ) before scaling to
 * multiple app instances.
 */
interface Bucket {
  count: number;
  windowStartMs: number;
}

const buckets = new Map<string, Bucket>();

export interface RateLimitOptions {
  maxAttempts: number;
  windowMs: number;
}

export const LOGIN_RATE_LIMIT: RateLimitOptions = { maxAttempts: 5, windowMs: 60_000 };

export function checkRateLimit(
  key: string,
  options: RateLimitOptions = LOGIN_RATE_LIMIT,
): { allowed: boolean; retryAfterMs: number } {
  const now = Date.now();
  const bucket = buckets.get(key);

  if (!bucket || now - bucket.windowStartMs > options.windowMs) {
    buckets.set(key, { count: 1, windowStartMs: now });
    return { allowed: true, retryAfterMs: 0 };
  }

  if (bucket.count >= options.maxAttempts) {
    return { allowed: false, retryAfterMs: options.windowMs - (now - bucket.windowStartMs) };
  }

  bucket.count += 1;
  return { allowed: true, retryAfterMs: 0 };
}

export function resetRateLimit(key: string): void {
  buckets.delete(key);
}
