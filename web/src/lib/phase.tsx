"use client";

/**
 * Day/night engine (docs/DESIGN.md section 2). The phase follows the real exchange session
 * from /v1/status (the chain's clock on fork and local profiles), never a timer. A change of
 * phase bumps `bells`, which the art uses to ring the closing (or opening) bell sequence; the
 * colour crossfade itself is the CSS transition on --phase. "Preview the close" flips the phase
 * locally for a few seconds so visitors can see the sequence at any time.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { Status } from "./api";
import { useStatus } from "./queries";

export type Phase = "day" | "night";

/** The resting look while the session is not known yet: the brand's night palette. It is only
 *  colour; badges and countdowns say the clock is being read and never claim open or closed. */
export const UNKNOWN_PHASE_LOOK: Phase = "night";

interface PhaseState {
  /** What the page shows (the live phase, or the preview). */
  phase: Phase;
  /** The real session phase; badges and countdowns use this, never the preview. */
  live: Phase;
  /** False until a real /v1/status has arrived (server or browser); never assume open. */
  known: boolean;
  status: Status | undefined;
  /** Wall-clock ms when `status` arrived, to advance its clock between refreshes. */
  statusAt: number;
  bells: number;
  previewing: boolean;
  previewClose: () => void;
  /** Show the other phase for a while (the header's day and night switch), then return. */
  previewToggle: () => void;
}

const PhaseContext = createContext<PhaseState | null>(null);

export function phaseFor(status: Pick<Status, "state"> | undefined, fallback: Phase): Phase {
  if (!status) return fallback;
  return status.state === "open" ? "day" : "night";
}

export function PhaseProvider({
  initial,
  children,
}: {
  /** The phase the server read from /v1/status, or null if it could not in time. */
  initial: Phase | null;
  children: React.ReactNode;
}) {
  const { data: status, dataUpdatedAt: statusAt } = useStatus();
  const known = status !== undefined || initial !== null;
  const live = phaseFor(status, initial ?? UNKNOWN_PHASE_LOOK);
  const [override, setOverride] = useState<Phase | null>(null);
  const phase = override ?? live;
  const [bells, setBells] = useState(0);
  const previous = useRef<Phase>(phase);
  const timers = useRef<number[]>([]);

  const wasKnown = useRef(known);
  useEffect(() => {
    document.documentElement.dataset.phase = phase;
    if (previous.current !== phase) {
      previous.current = phase;
      // Learning the session for the first time is not a bell: only real changes ring.
      if (wasKnown.current) setBells((b) => b + 1);
    }
    wasKnown.current = known;
  }, [phase, known]);

  useEffect(() => () => timers.current.forEach((t) => window.clearTimeout(t)), []);

  const previewClose = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    const later = (ms: number, fn: () => void) => timers.current.push(window.setTimeout(fn, ms));
    if (live === "night") {
      // Snap to day without a crossfade, then ring the closing bell into night.
      const root = document.documentElement;
      root.classList.add("no-phase-transition");
      setOverride("day");
      later(60, () => root.classList.remove("no-phase-transition"));
      later(400, () => setOverride("night"));
      later(6000, () => setOverride(null));
    } else {
      setOverride("night");
      later(8000, () => setOverride(null));
    }
  }, [live]);

  const previewToggle = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    const target: Phase = phase === "day" ? "night" : "day";
    if (target === live) {
      setOverride(null);
      return;
    }
    setOverride(target);
    timers.current.push(window.setTimeout(() => setOverride(null), 12000));
  }, [phase, live]);

  const value = useMemo(
    () => ({
      phase,
      live,
      known,
      status,
      statusAt,
      bells,
      previewing: override !== null,
      previewClose,
      previewToggle,
    }),
    [phase, live, known, status, statusAt, bells, override, previewClose, previewToggle],
  );
  return <PhaseContext.Provider value={value}>{children}</PhaseContext.Provider>;
}

export function usePhase(): PhaseState {
  const ctx = useContext(PhaseContext);
  if (!ctx) throw new Error("usePhase must be used inside PhaseProvider");
  return ctx;
}
