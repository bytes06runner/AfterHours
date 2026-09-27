"use client";

/**
 * Live risk board: every Stock Token on Robinhood Chain mainnet, its price feed's last update,
 * whether the feed is frozen now, and tonight's forecast bad case against the cushions of the
 * Morpho markets that lend against it. Read-only, from /v1/live/board.
 */
import { useMemo, useState } from "react";

import { liveErrorText, RETRY_TEXT, type LiveBoard } from "@/lib/api";
import { useLiveBoard } from "@/lib/queries";
import { formatPct } from "@/lib/time";

import { LiveLabel } from "./LiveLabel";
import { ZonedTime } from "./ZonedTime";

type Row = LiveBoard["stocks"][number];

function ago(seconds: number): string {
  if (seconds < 90) return "just now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h ago`;
  return `${Math.round(seconds / 86400)} days ago`;
}

function FeedState({ r }: { r: Row }) {
  if (!r.status || !r.updated_at) return <span>No feed reading</span>;
  const s = r.status;
  const color =
    s.state === "frozen"
      ? "var(--c-risk)"
      : s.state === "quiet"
        ? "var(--c-brass)"
        : "var(--c-safe)";
  const text =
    s.state === "frozen"
      ? "Frozen for the weekend"
      : s.state === "quiet"
        ? `No update for ${ago(s.age_seconds).replace(" ago", "")}`
        : "Updating";
  return (
    <span className="flex flex-col">
      <span className="flex items-center gap-2 font-semibold">
        <span
          aria-hidden="true"
          className="inline-block h-2.5 w-2.5 rounded-full"
          style={{ background: color }}
        />
        {text}
      </span>
      <span className="text-[14px]">
        Last update {ago(s.age_seconds)}: <ZonedTime iso={r.updated_at} />
      </span>
    </span>
  );
}

function Tonight({ r }: { r: Row }) {
  if (!r.tonight) return <span>No forecast</span>;
  const t = r.tonight;
  const seg: Record<string, string> = {
    earnings: "earnings night",
    weekend: "weekend",
    holiday: "holiday",
    overnight: "overnight",
  };
  return (
    <span className="flex flex-col">
      <span className="text-[21px] font-bold">{formatPct(t.bad_case_drop)}</span>
      <span className="text-[14px]">
        {seg[t.period.segment] ?? t.period.segment}, until <ZonedTime iso={t.period.ends} />
      </span>
    </span>
  );
}

function Markets({ r }: { r: Row }) {
  if (r.markets.length === 0) return <span className="text-[14px]">No USDG markets</span>;
  if (r.breached.length === 0)
    return (
      <span className="text-[14px]">
        Within every market&apos;s cushion ({r.markets.length} markets)
      </span>
    );
  const worst = r.markets.filter((m) => r.breached.includes(m.lltv));
  return (
    <span className="text-[14px]">
      <span className="font-semibold" style={{ color: "var(--c-risk)" }}>
        Beyond the cushion of {worst.length} of {r.markets.length} markets:
      </span>{" "}
      {worst.map((m) => `${formatPct(m.lltv)} LTV (${formatPct(m.cushion)})`).join(", ")}
    </span>
  );
}

export function RiskBoardView() {
  const q = useLiveBoard();
  const [filter, setFilter] = useState<"all" | "breach" | "frozen">("all");
  const rows = useMemo(() => {
    const all = [...(q.data?.stocks ?? [])].sort(
      (a, b) => (b.tonight?.bad_case_drop ?? -1) - (a.tonight?.bad_case_drop ?? -1),
    );
    if (filter === "breach") return all.filter((r) => r.breached.length > 0);
    if (filter === "frozen") return all.filter((r) => r.status?.state === "frozen");
    return all;
  }, [q.data, filter]);
  const d = q.data;
  const frozen = d?.stocks.filter((r) => r.status?.state === "frozen").length ?? 0;
  const alpha = d?.stocks.find((r) => r.tonight)?.tonight?.alpha;
  const oneIn = alpha ? Math.round(1 / alpha) : null;
  return (
    <div className="mx-auto max-w-[1440px] px-4 pb-24 sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Live risk board</h1>
      <div className="mt-3">
        <LiveLabel block={d?.block} />
      </div>
      <p className="mt-4 max-w-[70ch] text-[18px]">
        Every Stock Token on {d?.network ?? "Robinhood Chain"}: when its price feed last moved,
        whether it is frozen right now, and tonight&apos;s bad case, the fall we expect to be beaten
        only about {oneIn ? `1 night in ${oneIn}` : "rarely"}. If that fall is bigger than a lending
        market&apos;s cushion, a loan at that market&apos;s limit could be left with bad debt.
      </p>
      {d && (
        <p className="mt-2 text-[16px] font-semibold">
          {frozen} of {d.stocks.length} feeds are frozen now. Read at <ZonedTime iso={d.as_of} />.
        </p>
      )}
      <div role="group" aria-label="Filter" className="mt-6 flex flex-wrap gap-2">
        {(
          [
            ["all", "All stocks"],
            ["breach", "Beyond a cushion tonight"],
            ["frozen", "Frozen now"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={filter === k}
            onClick={() => setFilter(k)}
            className={`btn !min-h-[40px] !text-[16px] ${filter === k ? "btn-brass" : "btn-quiet"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {q.isError && (
        <p role="alert" className="mt-8 text-[18px]">
          {liveErrorText(q.error, "Can't reach Robinhood Chain right now.")} {RETRY_TEXT}
        </p>
      )}
      {!d && !q.isError && (
        <p aria-busy="true" className="mt-8 min-h-[400px]">
          Reading every Stock Token price feed on mainnet.
        </p>
      )}
      {d && (
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-left">
            <caption className="sr-only">Stock Token feeds and tonight&apos;s bad case</caption>
            <thead>
              <tr className="text-[14px]">
                {[
                  "Stock",
                  "Price (USD)",
                  "Price feed",
                  "Tonight's bad case",
                  "Lending markets",
                ].map((h) => (
                  <th key={h} className="border-b-[1.25px] border-rule py-2 pr-4 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.symbol} data-testid="board-row" className="align-top">
                  <td className="border-b-[1.25px] border-rule py-3 pr-4 font-display text-[24px]">
                    {r.symbol}
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4 text-[18px] font-semibold">
                    {r.price !== null
                      ? r.price.toLocaleString("en-US", { maximumFractionDigits: 2 })
                      : "n/a"}
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <FeedState r={r} />
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <Tonight r={r} />
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <Markets r={r} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-4">No stock matches this filter right now.</p>}
        </div>
      )}
      <p className="mt-6 max-w-[70ch] text-[14px]">
        Frozen: inside the weekend window (Friday 20:00 to Sunday 20:00 New York) in which, over the
        8 weekends we measured, these feeds posted nothing. Forecasts are the shipped model&apos;s
        1-in-100 bad case for the closed period now in progress or the next one. Not financial
        advice.
      </p>
    </div>
  );
}
