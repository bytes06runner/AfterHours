"use client";

/**
 * Header switch: preview the other phase on any page (the whole site crossfades and the bell
 * rings). It is a preview; the session badge keeps showing the real exchange session.
 */
import { usePhase } from "@/lib/phase";

export function DayNightSwitch() {
  const { phase, previewToggle, previewing } = usePhase();
  const night = phase === "night";
  const label = night ? "See it by day" : "See it at night";
  return (
    <button
      type="button"
      onClick={previewToggle}
      aria-pressed={previewing}
      aria-label={`${label} (preview)`}
      title={`${label} (preview)`}
      className="daynight relative inline-flex h-10 w-[72px] shrink-0 items-center rounded-full border-[1.25px] border-rule bg-surface"
    >
      <span aria-hidden="true" className="daynight-knob">
        <svg viewBox="0 0 24 24" className="h-5 w-5">
          <g className="daynight-sun">
            <circle cx="12" cy="12" r="5" fill="var(--c-brass)" />
            {Array.from({ length: 8 }, (_, i) => {
              const a = (i * Math.PI) / 4;
              return (
                <line
                  key={i}
                  x1={12 + Math.cos(a) * 7.5}
                  y1={12 + Math.sin(a) * 7.5}
                  x2={12 + Math.cos(a) * 10}
                  y2={12 + Math.sin(a) * 10}
                  stroke="var(--c-brass)"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              );
            })}
          </g>
          <path
            className="daynight-moon"
            d="M15 3.5a8.5 8.5 0 1 0 5.5 14.9A7 7 0 0 1 15 3.5z"
            fill="var(--c-text)"
          />
        </svg>
      </span>
    </button>
  );
}
