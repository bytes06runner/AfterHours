"use client";

import { useEffect, useState } from "react";

/** Wall-clock milliseconds, refreshed every `intervalMs`. */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

/** The exchange clock "now": the status snapshot advanced by the time since it arrived. */
export function clockNow(
  statusNow: string | undefined,
  receivedAt: number,
  wallNow: number,
): Date | undefined {
  if (!statusNow || !receivedAt) return undefined;
  return new Date(new Date(statusNow).getTime() + Math.max(0, wallNow - receivedAt));
}
