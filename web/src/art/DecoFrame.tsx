"use client";

/**
 * DecoFrame: a double-rule frame with stepped corners (no radius, no shadow). Drawn in SVG at
 * the element's measured pixel size so the steps stay square at every width.
 */
import { useEffect, useRef, useState } from "react";

function stepped(w: number, h: number, inset: number, step: number): string {
  const a = inset;
  const b = inset + step;
  return [
    `M${b} ${a}`,
    `H${w - b}`,
    `V${b - step + step}`,
    `H${w - a}`,
    `V${h - b}`,
    `H${w - b}`,
    `V${h - a}`,
    `H${b}`,
    `V${h - b}`,
    `H${a}`,
    `V${b}`,
    `H${b}`,
    "Z",
  ].join(" ");
}

export function DecoFrame({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const box = entry.contentRect;
      setSize({ w: Math.round(box.width), h: Math.round(box.height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} className={`relative p-[18px] ${className}`}>
      {size && (
        <svg
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox={`0 0 ${size.w} ${size.h}`}
        >
          <path
            d={stepped(size.w, size.h, 1, 16)}
            fill="none"
            stroke="var(--a-brass)"
            strokeWidth={2}
          />
          <path
            d={stepped(size.w, size.h, 8, 12)}
            fill="none"
            stroke="var(--a-rule)"
            strokeWidth={1.25}
          />
        </svg>
      )}
      <div
        className="stepped relative overflow-hidden"
        style={{ "--step": "10px" } as React.CSSProperties}
      >
        {children}
      </div>
    </div>
  );
}
