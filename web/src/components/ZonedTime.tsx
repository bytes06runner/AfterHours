"use client";

/**
 * A session time in New York (the exchange's clock) and, when the visitor is elsewhere, in their
 * own time zone: "Fri 4:00 PM New York (Sat 1:30 AM your time)". The visitor's zone is read on
 * the client only, so the server and the first client render match.
 */
import { useSyncExternalStore } from "react";

import { NEW_YORK } from "@/lib/time";

const noop = () => () => undefined;
const clientZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
const serverZone = () => null;

export function useVisitorZone(): string | null {
  return useSyncExternalStore(noop, clientZone, serverZone);
}

export function formatIn(iso: string | Date, timeZone: string, withDay = true): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone,
    ...(withDay ? { weekday: "short", month: "short", day: "numeric" } : {}),
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function ZonedTime({ iso, withDay = true }: { iso: string | Date; withDay?: boolean }) {
  const zone = useVisitorZone();
  const ny = formatIn(iso, NEW_YORK, withDay);
  const local = zone && zone !== NEW_YORK ? formatIn(iso, zone, withDay) : null;
  const stamp = typeof iso === "string" ? iso : iso.toISOString();
  return (
    <time dateTime={stamp}>
      {ny} New York
      {local && <span className="whitespace-nowrap"> ({local} your time)</span>}
    </time>
  );
}
