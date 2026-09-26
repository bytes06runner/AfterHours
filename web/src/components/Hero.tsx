"use client";

import Link from "next/link";

import { DecoFrame } from "@/art/DecoFrame";
import { ExchangeFacade } from "@/art/ExchangeFacade";
import { TickerRibbon } from "@/art/TickerRibbon";
import { usePhase } from "@/lib/phase";
import { clockNow, useNow } from "@/lib/useNow";

import { BellCountdown } from "./BellCountdown";

const COPY = {
  day: {
    title: ["The market is open.", "Lending runs at full speed."],
    sub: "When the bell rings, Afterhours pulls back first.",
  },
  night: {
    title: ["The market is closed.", "Stock Tokens aren't."],
    sub: "Afterhours moved lender money to safer markets before the bell. Here's why.",
  },
};

export function Hero() {
  const { phase, status, statusAt, bells, previewing, previewClose } = usePhase();
  const wall = useNow(30_000);
  const clock = clockNow(status?.now, statusAt, wall)?.toISOString();
  const copy = COPY[phase];
  return (
    <section aria-labelledby="hero-title" className="mx-auto max-w-[1280px] px-4 sm:px-8">
      <DecoFrame>
        <ExchangeFacade
          bells={bells}
          clockIso={clock}
          ticker={<TickerRibbon className="hidden md:flex" />}
        />
      </DecoFrame>
      {/* On phones the ribbon inside the art would be too small to read. */}
      <div className="mt-3 h-10 overflow-hidden rounded-[10px] md:hidden">
        <TickerRibbon />
      </div>
      <div className="mt-10 grid gap-10 md:grid-cols-[1.4fr_1fr] md:items-end">
        <div>
          <h1 id="hero-title" className="text-[48px] leading-[1.02] lg:text-[64px] xl:text-[88px]">
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
    </section>
  );
}
