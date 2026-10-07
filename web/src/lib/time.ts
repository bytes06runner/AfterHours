/** Time helpers. The exchange clock is New York time. */

export const NEW_YORK = "America/New_York";

/** Hours, minutes and seconds of a New York wall clock at `iso`. */
export function newYorkClock(iso: string | Date): { h: number; m: number; s: number } {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: NEW_YORK,
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hourCycle: "h23",
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value ?? 0);
  return { h: get("hour"), m: get("minute"), s: get("second") };
}

/** Split seconds into two-digit hours (may exceed 99 as days), minutes and seconds. */
export function countdownParts(totalSeconds: number): { h: string; m: string; s: string } {
  const t = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return { h: pad(Math.min(h, 99)), m: pad(m), s: pad(s) };
}

export function formatUsd(n: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(n);
}

export function formatPct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

/**
 * How often the bad case is beaten: the forecast's target and, when the API gives it, the
 * measured share on held-out years for this kind of closed period (never "1 in 100" alone,
 * which is only the target).
 */
export function coverageText(t: {
  alpha: number;
  period: { segment: string };
  held_out_miss_rate?: number | null;
  held_out_years?: number[] | null;
}): string {
  const target = `the forecast aims for a fall beyond it on ${formatPct(t.alpha, 0)} of closed periods`;
  const miss = t.held_out_miss_rate;
  if (!miss) return target;
  const years = t.held_out_years ? ` ${t.held_out_years[0]} to ${t.held_out_years[1]}` : "";
  return `${target}; on held-out years${years} it was beaten on ${formatPct(miss, 2)} of ${t.period.segment} periods, about 1 in ${Math.round(1 / miss)}`;
}
