export function fmt(n: number): string {
  return (n < 0 ? "-$" : "$") + Math.abs(n).toFixed(2).replace(/\.00$/, "");
}

export function pctS(n: number): string {
  return Math.round(n * 100) + "%";
}

export function initials(name: string): string {
  const words = name.replace(/[^A-Za-z0-9 ]/g, " ").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

const AVATAR_PALETTE = ["var(--blue)", "var(--purple)", "var(--orange)", "var(--yellow)", "var(--pink)", "var(--pos)"];

/** Deterministic color pick so the same name always gets the same chip color. */
export function colorForLabel(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  }
  return AVATAR_PALETTE[hash % AVATAR_PALETTE.length];
}
