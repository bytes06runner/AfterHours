"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api, RETRY_TEXT } from "@/lib/api";
import { usePhase } from "@/lib/phase";
import { useConfig } from "@/lib/queries";

import { Telegram } from "./Telegram";
import { ZonedTime } from "./ZonedTime";

function nextPlan(nextClose: string | undefined, preCloseMinutes: number | undefined): Date | null {
  if (!nextClose || preCloseMinutes === undefined) return null;
  return new Date(new Date(nextClose).getTime() - preCloseMinutes * 60_000);
}

/** Every reason the bot anchored onchain, newest first. */
export function LedgerView() {
  const [stock, setStock] = useState<string>("");
  const { status } = usePhase();
  const { data: pub } = useConfig();
  const query = useInfiniteQuery({
    queryKey: ["reasons", stock || "all"],
    queryFn: ({ pageParam }) => api.reasons(pageParam, stock || undefined),
    initialPageParam: 0,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const cards = query.data?.pages.flatMap((p) => p.items) ?? [];
  const total = query.data?.pages[0]?.total ?? 0;
  const symbols = Array.from(new Set(cards.map((c) => c.stock))).sort();
  const when = nextPlan(status?.next_close, pub?.schedule.pre_close_minutes);
  return (
    <div className="mx-auto max-w-[1280px] px-4 pb-24 sm:px-8">
      <header className="mt-8 flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="text-[48px] lg:text-[64px]">The ledger</h1>
          <p className="mt-3 text-[18px]">
            Every move the vault made, with the reason it gave at the time. Each reason&apos;s hash
            is recorded onchain; check any of them from your browser.
          </p>
        </div>
        <label className="flex flex-col gap-1 text-[14px] font-semibold">
          Stock
          <select
            value={stock}
            onChange={(e) => setStock(e.target.value)}
            className="min-h-[44px] rounded-[10px] border-[1.25px] border-rule bg-bg px-3 text-[16px]"
          >
            <option value="">All stocks</option>
            {(symbols.length ? symbols : stock ? [stock] : []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </header>
      {query.isError && (
        <p role="alert" className="mt-10 text-[18px]">
          Can&apos;t reach the Afterhours API. {RETRY_TEXT}
        </p>
      )}
      {query.isSuccess && cards.length === 0 && (
        <p className="mt-10 text-[18px]">
          No moves yet.{" "}
          {when ? (
            <>
              The next plan runs at the pre-close check, <ZonedTime iso={when} />.
            </>
          ) : (
            "The next plan runs at the next pre-close check."
          )}
        </p>
      )}
      <p className="mt-8 text-[14px]">{total > 0 && `${total} reasons`}</p>
      <ol className="relative mt-4 flex flex-col gap-10 border-l-[2px] border-brass pl-6 sm:pl-10">
        {cards.map((card) => (
          <li key={card.id} className="relative">
            <span
              aria-hidden="true"
              className="absolute -left-[33px] top-6 h-4 w-4 rounded-full border-[2px] border-brass bg-bg sm:-left-[49px]"
            />
            <Telegram card={card} />
          </li>
        ))}
      </ol>
      {query.hasNextPage && (
        <button
          type="button"
          className="btn btn-quiet mt-10"
          onClick={() => void query.fetchNextPage()}
        >
          Show older reasons
        </button>
      )}
    </div>
  );
}
