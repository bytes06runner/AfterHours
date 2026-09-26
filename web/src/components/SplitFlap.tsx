"use client";

/** SplitFlap: mechanical digits. A digit flips only when its value changes. */
import { AnimatePresence, motion, useReducedMotion } from "motion/react";

function Flap({ char }: { char: string }) {
  const reduce = useReducedMotion();
  return (
    <span
      className="relative inline-flex h-[1.35em] w-[0.92em] items-center justify-center overflow-hidden rounded-[6px] bg-surface font-sans font-bold text-ink"
      style={{ perspective: "400px", boxShadow: "none" }}
    >
      <AnimatePresence initial={false} mode="popLayout">
        <motion.span
          key={char}
          initial={reduce ? { opacity: 0 } : { rotateX: -90, opacity: 0.2 }}
          animate={reduce ? { opacity: 1 } : { rotateX: 0, opacity: 1 }}
          exit={reduce ? { opacity: 0 } : { rotateX: 90, opacity: 0.2 }}
          transition={{ duration: 0.24, ease: [0.2, 0.8, 0.2, 1] }}
          className="inline-block"
        >
          {char}
        </motion.span>
      </AnimatePresence>
      <span aria-hidden="true" className="absolute inset-x-0 top-1/2 border-t border-bg/70" />
    </span>
  );
}

export function SplitFlap({ value, label }: { value: string; label: string }) {
  return (
    <span role="text" aria-label={label} className="inline-flex gap-[0.12em] tabular-nums">
      {value.split("").map((c, i) =>
        /[0-9]/.test(c) ? (
          <Flap key={i} char={c} />
        ) : (
          <span key={i} aria-hidden="true" className="px-[0.04em] text-brass">
            {c}
          </span>
        ),
      )}
    </span>
  );
}
