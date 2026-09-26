"use client";

import { usePhase } from "@/lib/phase";
import { clockNow, useNow } from "@/lib/useNow";

/** Seconds from the exchange clock to `target`, ticking every second. */
export function useSecondsTo(target: string | undefined): number {
  const { status, statusAt } = usePhase();
  const wall = useNow(1000);
  const now = clockNow(status?.now, statusAt, wall);
  if (!target || !now) return 0;
  return Math.max(0, Math.floor((new Date(target).getTime() - now.getTime()) / 1000));
}

function human(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/** "Exchange open" or "Afterhours", with the time until the next bell. */
export function SessionBadge() {
  const { live, status } = usePhase();
  const open = live === "day";
  const left = useSecondsTo(open ? status?.next_close : status?.next_open);
  return (
    <span className="badge" aria-live="polite">
      <span
        aria-hidden="true"
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: open ? "var(--c-safe)" : "var(--c-brass)" }}
      />
      {open ? "Exchange open" : "Afterhours"}
      {status && (
        <span className="font-normal">
          {open ? "closes in" : "opens in"} {human(left)}
        </span>
      )}
    </span>
  );
}
