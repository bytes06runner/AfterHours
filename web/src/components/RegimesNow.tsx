"use client";

/**
 * Landing: how every Stock Token is priced right now. Frozen today; thin tomorrow, if weekend
 * trading comes to the feeds. Counts per regime and the tokens whose price deserves the least
 * trust, each with its one plain line. Live from /v1/live/regimes.
 */
import Link from "next/link";

import type { LiveRegimeT } from "@/lib/api";
import { useLiveRegimes } from "@/lib/queries";

import { LiveLabel } from "./LiveLabel";
import { RegimeBadge, RegimeDot } from "./RegimeBadge";
import { ZonedTime } from "./ZonedTime";

const ORDER: LiveRegimeT["regime"][] = ["regular", "extended", "weekend_venue", "frozen"];
const NAME: Record<LiveRegimeT["regime"], string> = {
  regular: "Regular session",
  extended: "Extended hours",
  weekend_venue: "Weekend price",
  frozen: "Frozen",
};

export function RegimesNow({ show = 3 }: { show?: number }) {
  const { data: d } = useLiveRegimes();
  const weakest = d
    ? [...d.tokens]
        .filter((t) => t.quality.score !== null)
        .sort((a, b) => (a.quality.score ?? 0) - (b.quality.score ?? 0))
        .slice(0, show)
    : [];
  return (
    <div className="mt-6" data-testid="regimes-now">
      <div className="flex flex-wrap items-center gap-3">
        <LiveLabel block={d?.block} />
        {d && (
          <span className="text-[14px]">
            Read at <ZonedTime iso={d.as_of} />
          </span>
        )}
      </div>
      {!d && (
        <p aria-busy="true" className="mt-4 min-h-[180px] text-[18px]">
          Reading how every Stock Token is priced right now.
        </p>
      )}
      {d && (
        <>
          <ul
            className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4"
            aria-label="Stock Tokens by price regime"
          >
            {ORDER.map((k) => (
              <li
                key={k}
                className="flex flex-col gap-1 rounded-[12px] border-[1.25px] border-rule bg-surface p-4"
              >
                <span className="flex items-center gap-2 text-[16px] font-semibold">
                  <RegimeDot regime={k} />
                  {NAME[k]}
                </span>
                <span className="font-display text-[48px] leading-none tabular-nums">
                  {d.counts[k] ?? 0}
                </span>
                <span className="text-[14px]">of {d.tokens.length} Stock Tokens</span>
              </li>
            ))}
          </ul>
          {weakest.length > 0 && (
            <div className="mt-6">
              <h3 className="text-[21px] font-semibold">Least trustworthy prices right now</h3>
              <ul className="mt-3 flex flex-col gap-3">
                {weakest.map((t) => (
                  <li key={t.symbol} className="flex flex-col gap-1 sm:flex-row sm:gap-4">
                    <span className="w-20 shrink-0 font-display text-[24px]">{t.symbol}</span>
                    <span className="flex flex-col gap-1">
                      <RegimeBadge r={t} size="sm" />
                      <span className="max-w-[72ch] text-[16px]">{t.line}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="mt-4 text-[14px]">
            <Link href="/live" className="underline">
              Every Stock Token on the live risk board
            </Link>
            . How regimes and scores are worked out: docs/REGIME.md in the repository.
          </p>
        </>
      )}
    </div>
  );
}
