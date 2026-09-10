/**
 * All monetary values in this codebase are integer cents (minor units).
 * Never store or compute currency as floating point dollars.
 */
export type Cents = number;

export function dollarsToCents(dollars: number): Cents {
  return Math.round(dollars * 100);
}

export function centsToDollars(cents: Cents): number {
  return cents / 100;
}

export function formatCents(cents: Cents, currency = "USD", locale = "en-US"): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency }).format(
    centsToDollars(cents),
  );
}

export function addCents(...values: Cents[]): Cents {
  return values.reduce((sum, v) => sum + Math.trunc(v), 0);
}

export function sumCents(values: Cents[]): Cents {
  return addCents(...values);
}

export function subtractCents(a: Cents, b: Cents): Cents {
  return Math.trunc(a) - Math.trunc(b);
}

/**
 * Split `total` cents into `parts` shares as evenly as possible, with the
 * remainder distributed one cent at a time starting at index 0, so the
 * shares always sum back to `total` exactly (no floating point drift).
 */
export function splitCentsEvenly(total: Cents, parts: number): Cents[] {
  if (parts <= 0) throw new Error("parts must be > 0");
  const base = Math.trunc(total / parts);
  const remainder = total - base * parts;
  return Array.from({ length: parts }, (_, i) => base + (i < remainder ? 1 : 0));
}

export function percentOfCents(cents: Cents, percent: number): Cents {
  return Math.round(cents * (percent / 100));
}
