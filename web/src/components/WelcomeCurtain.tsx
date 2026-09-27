"use client";

/**
 * The welcome sequence (first visit per browser session, landing page only). Bronze deco doors
 * close over the page with the bell and the name; a brass bar fills as the page really gets
 * ready (fonts, the exchange clock from /v1/status, the report card), the bell rings, and the
 * doors swing open onto the exchange. Skippable (button or Escape); never shown with reduced
 * motion; never blocks for more than MAX_MS.
 */
import { useEffect, useRef, useState } from "react";

import { useReportCard, useStatus } from "@/lib/queries";

const KEY = "ah:welcomed";
const MIN_MS = 1400;
const MAX_MS = 4200;
const RING_MS = 900;
const OPEN_MS = 1150;

type Stage = "hidden" | "loading" | "ringing" | "opening";

function seen(): boolean {
  try {
    return window.sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
function remember() {
  try {
    window.sessionStorage.setItem(KEY, "1");
  } catch {
    /* private mode: show again next time */
  }
}

function Door({ side }: { side: "left" | "right" }) {
  return (
    <div className={`door door-${side}`} aria-hidden="true">
      <div className="door-panel" />
      <span className="door-handle" />
    </div>
  );
}

/** The seam medallion: the bell inside a stepped disc, rays behind it. */
function Medallion({ ringing }: { ringing: boolean }) {
  return (
    <svg viewBox="0 0 320 200" className="w-[min(320px,80vw)]" aria-hidden="true">
      {Array.from({ length: 17 }, (_, i) => {
        const a = Math.PI - (i * Math.PI) / 16;
        return (
          <line
            key={i}
            x1={160 + Math.cos(a) * 62}
            y1={170 - Math.sin(a) * 62}
            x2={160 + Math.cos(a) * 150}
            y2={170 - Math.sin(a) * 150}
            stroke="var(--night-brass)"
            strokeWidth="2"
            opacity="0.5"
          />
        );
      })}
      <circle
        cx="160"
        cy="118"
        r="58"
        fill="var(--night-bg)"
        stroke="var(--night-brass)"
        strokeWidth="2"
      />
      <circle cx="160" cy="118" r="50" fill="none" stroke="var(--night-rule)" strokeWidth="1.25" />
      <g transform="translate(128 86)">
        <g className={ringing ? "a-bell ringing" : "a-bell"}>
          <rect x="31" y="6" width="2" height="8" fill="var(--night-brass)" />
          <path
            d="M32 13c-7 0-8.5 7-8.5 14.5L20 35h24l-3.5-7.5C40.5 20 39 13 32 13z"
            fill="var(--night-brass)"
          />
          <circle cx="32" cy="38.5" r="3" fill="var(--night-brass)" />
        </g>
        <path d="M16 46h32M12 50h40" stroke="var(--night-brass)" strokeWidth="2" />
      </g>
    </svg>
  );
}

export function WelcomeCurtain() {
  const [stage, setStage] = useState<Stage>("hidden");
  const [fonts, setFonts] = useState(false);
  const status = useStatus();
  const report = useReportCard();
  const start = useRef(0);
  const timers = useRef<number[]>([]);

  // Decide once, on the client, whether to show it.
  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || seen()) return;
    start.current = performance.now();
    const t = window.setTimeout(() => setStage("loading"), 0);
    void document.fonts?.ready.then(() => setFonts(true));
    return () => window.clearTimeout(t);
  }, []);

  const steps = [
    { label: "Lighting the lamps", done: fonts },
    { label: "Reading the exchange clock", done: Boolean(status.data) || status.isError },
    { label: "Opening the books", done: Boolean(report.data) || report.isError },
  ];
  const done = steps.filter((s) => s.done).length;
  const ready = done === steps.length;

  const finish = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    remember();
    setStage("hidden");
  };

  // Ready (or out of time): ring, then open, then remove.
  useEffect(() => {
    if (stage !== "loading") return;
    const elapsed = performance.now() - start.current;
    const wait = ready ? Math.max(0, MIN_MS - elapsed) : Math.max(0, MAX_MS - elapsed);
    const t = window.setTimeout(() => setStage("ringing"), wait);
    return () => window.clearTimeout(t);
  }, [stage, ready]);
  useEffect(() => {
    if (stage === "ringing") {
      const t = window.setTimeout(() => setStage("opening"), RING_MS);
      timers.current.push(t);
    }
    if (stage === "opening") {
      const t = window.setTimeout(finish, OPEN_MS);
      timers.current.push(t);
    }
  }, [stage]);

  useEffect(() => {
    if (stage === "hidden") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") finish();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stage]);

  if (stage === "hidden") return null;
  const current = steps.find((s) => !s.done)?.label ?? "Ringing the bell";
  return (
    <div className={`curtain curtain-${stage}`} data-testid="welcome">
      <div className="curtain-door curtain-left">
        <Door side="left" />
      </div>
      <div className="curtain-door curtain-right">
        <Door side="right" />
      </div>
      <div className="curtain-center">
        <Medallion ringing={stage === "ringing"} />
        <div className="curtain-plaque">
          <p className="font-display text-[44px] leading-none text-[var(--night-text)] sm:text-[80px]">
            Afterhours
          </p>
          <div className="mx-auto mt-5 h-[6px] w-[min(320px,64vw)] overflow-hidden rounded-full bg-[var(--night-rule)]">
            <div
              className="h-full rounded-full bg-[var(--night-brass)]"
              style={{
                width: `${((stage === "loading" ? done : steps.length) / steps.length) * 100}%`,
                transition: "width 500ms var(--ease-ui)",
              }}
            />
          </div>
          <p role="status" className="mt-3 text-[16px] font-semibold text-[var(--night-text)]">
            {current}
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={finish}
        className="curtain-skip btn btn-quiet !min-h-[40px] !border-[var(--night-text)] !text-[16px] !text-[var(--night-text)]"
      >
        Skip
      </button>
    </div>
  );
}
