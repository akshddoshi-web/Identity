const DAY_MS = 24 * 60 * 60 * 1000;

export interface ChargeCountdown {
  days: number;
  label: string;
  urgent: boolean; // due within 3 days
  overdue: boolean;
}

export function chargeCountdown(nextChargeDate: string, now: Date = new Date()): ChargeCountdown {
  const next = new Date(nextChargeDate + "T00:00:00");
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((next.getTime() - today.getTime()) / DAY_MS);

  if (days < 0) return { days, label: "Overdue", urgent: true, overdue: true };
  if (days === 0) return { days, label: "Charges today", urgent: true, overdue: false };
  if (days === 1) return { days, label: "Charges tomorrow", urgent: true, overdue: false };
  return { days, label: `Charges in ${days} days`, urgent: days <= 3, overdue: false };
}
