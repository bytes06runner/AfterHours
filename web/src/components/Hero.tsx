"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { ExchangeFacade } from "@/art/ExchangeFacade";
import { TickerRibbon } from "@/art/TickerRibbon";
import { usePhase } from "@/lib/phase";
import { clockNow, useNow } from "@/lib/useNow";

import { BellCountdown } from "./BellCountdown";
import { WelcomeCurtain } from "./WelcomeCurtain";

/** Wide screens get the wide drawing (the art band then fills the width). */
function useWide(): boolean {
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const update = () => setWide(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);
  return wide;
}

/** Scroll parallax for the hero art: sets --hero-scroll while the art is on screen. */
function useHeroScroll() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const top = el.getBoundingClientRect().top;
      const past = Math.max(0, Math.min(el.offsetHeight, -top));
      el.style.setProperty("--hero-scroll", String(Math.round(past)));
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
  return ref;
}

const COPY = {
  day: {
    title: ["The market is open.", "Lending runs at full speed."],
    sub: "When the bell rings, Afterhours pulls back first.",
  },
  night: {
    title: ["The market is closed.", "Stock Tokens aren't."],
    sub: "Afterhours moved lender money to safer markets before the bell. Here's why.",
  },
  // Until /v1/status answers: say nothing about whether the exchange is open.
  unknown: {
    title: ["Stock Tokens never close.", "Their price feeds do."],
    sub: "Reading the exchange clock.",
  },
};

export function Hero() {
  const { phase, known, status, statusAt, bells, previewing, previewClose } = usePhase();
  const wall = useNow(30_000);
  const clock = clockNow(status?.now, statusAt, wall)?.toISOString();
  const copy = COPY[known || previewing ? phase : "unknown"];
  const art = useHeroScroll();
  const wide = useWide();
  return (
    <section aria-labelledby="hero-title">
      <WelcomeCurtain />
      <div ref={art} className="hero-art relative w-full overflow-hidden">
        <ExchangeFacade
          wide={wide}
          bells={bells}
          clockIso={clock}
          ticker={<TickerRibbon className="hidden md:flex" />}
        />
        <div aria-hidden="true" className="hero-rule hero-rule-top" />
        <div aria-hidden="true" className="hero-rule hero-rule-bottom" />
      </div>
      <div className="mx-auto max-w-[1440px] px-4 sm:px-8">
        {/* On phones the ribbon inside the art would be too small to read. */}
        <div className="mt-3 h-10 overflow-hidden rounded-[10px] md:hidden">
          <TickerRibbon />
        </div>
        <div className="mt-10 grid gap-10 md:grid-cols-[1.4fr_1fr] md:items-end">
          <div>
            <h1
              id="hero-title"
              className="text-[48px] leading-[1.02] lg:text-[64px] xl:text-[88px]"
            >
              {copy.title[0]}
              <br />
              {copy.title[1]}
            </h1>
            <p className="mt-6 text-[21px]">{copy.sub}</p>
          </div>
          <div className="flex flex-col gap-6">
            <BellCountdown />
            <div className="flex flex-wrap gap-3">
              <Link href="/vault" className="btn btn-brass">
                Open the vault
              </Link>
              <button
                type="button"
                className="btn btn-quiet"
                onClick={previewClose}
                aria-pressed={previewing}
              >
                Preview the close
              </button>
            </div>
            {previewing && (
              <p className="text-[14px]">Preview only. The real session is unchanged.</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
