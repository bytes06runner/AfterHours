"use client";

/**
 * Curator view: for every live USDG Morpho market lending against a Stock Token on mainnet,
 * tonight's bad case against the market's cushion, the highest LLTV that survives it, and one
 * recommendation. Read-only, from /v1/live/curator (engine/afterhours/live/curator.py).
 */
import { useMemo, useState } from "react";

import { type Curator, liveErrorText, RETRY_TEXT } from "@/lib/api";
import { useLiveCurator } from "@/lib/queries";
import { coverageText, formatPct } from "@/lib/time";

import { LiveLabel } from "./LiveLabel";
import { ZonedTime } from "./ZonedTime";

type Row = Curator["markets"][number];
type Rec = Row["recommendation"];

const COLOR: Record<Rec, string> = {
  reduce_cap: "var(--c-risk)",
  do_not_increase: "var(--c-risk)",
  watch: "var(--c-brass)",
  survives: "var(--c-safe)",
  no_forecast: "var(--c-rule)",
};

const usd = (x: number) => x.toLocaleString("en-US", { maximumFractionDigits: 0 });

/** The cushion as a track, the vault's margin line on it, and tonight's bad case as a bar. */
function CushionBar({ r }: { r: Row }) {
  if (r.bad_case_drop === null) return <span className="text-[14px]">No forecast tonight</span>;
  const scale = Math.max(r.cushion, r.bad_case_drop) * 1.1;
  const pos = (x: number) => `${Math.min(100, (x / scale) * 100)}%`;
  return (
    <span className="flex min-w-[220px] flex-col gap-1">
      <span className="flex items-baseline gap-2">
        <span
          className="text-[21px] font-bold"
          style={{ color: r.breach ? COLOR.reduce_cap : undefined }}
        >
          {formatPct(r.bad_case_drop)}
        </span>
        <span className="text-[14px]">against a {formatPct(r.cushion)} cushion</span>
      </span>
      <span
        role="img"
        aria-label={`Bad case ${formatPct(r.bad_case_drop)}, cushion ${formatPct(r.cushion)}, vault margin ${formatPct(r.margin_limit)}`}
        className="relative block h-3 w-full rounded-full border-[1.25px] border-rule"
      >
        <span
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: pos(r.bad_case_drop), background: COLOR[r.recommendation] }}
        />
        <span
          aria-hidden="true"
          className="absolute -top-1 h-5 w-[2px] bg-ink"
          style={{ left: pos(r.cushion) }}
        />
        <span
          aria-hidden="true"
          className="absolute -top-0.5 h-4 w-[1.25px] bg-ink opacity-50"
          style={{ left: pos(r.margin_limit) }}
        />
      </span>
      {r.tonight && (
        <span className="text-[14px]">
          {r.tonight.period.segment}, until <ZonedTime iso={r.tonight.period.ends} />
        </span>
      )}
    </span>
  );
}

function Survives({ r }: { r: Row }) {
  if (r.bad_case_drop === null) return <span>n/a</span>;
  return (
    <span className="flex flex-col">
      <span className="text-[21px] font-bold">
        {r.highest_surviving_lltv !== null ? formatPct(r.highest_surviving_lltv) : "None"}
      </span>
      <span className="text-[14px]">
        {r.highest_lltv_with_margin !== null
          ? `${formatPct(r.highest_lltv_with_margin)} with the vault's margin`
          : "none with the vault's margin"}
      </span>
    </span>
  );
}

function Liquidity({ r }: { r: Row }) {
  return (
    <span className="flex flex-col text-[14px]">
      <span className="text-[18px] font-semibold">{formatPct(r.utilization)} lent</span>
      <span>
        {usd(r.borrowed_usdg)} of {usd(r.supplied_usdg)} USDG
      </span>
      <span>Exit liquidity {usd(r.exit_liquidity_usdg)} USDG</span>
      <span>
        {r.borrowers
          ? `${r.borrowers.count} ${r.borrowers.count === 1 ? "borrower" : "borrowers"}, largest ${formatPct(r.borrowers.top_share)}`
          : r.borrowed_usdg > 0
            ? "Borrowers: still scanning"
            : "No borrowers"}
      </span>
    </span>
  );
}

function Recommendation({ r }: { r: Row }) {
  return (
    <span className="flex max-w-[52ch] flex-col gap-1">
      <span className="flex items-center gap-2 font-semibold">
        <span
          aria-hidden="true"
          className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ background: COLOR[r.recommendation] }}
        />
        {r.label}
      </span>
      <span className="text-[14px]">{r.reason}</span>
    </span>
  );
}

const FILTERS = [
  ["all", "All markets"],
  ["act", "Cut or hold caps"],
  ["watch", "Watch"],
  ["survives", "Survives"],
] as const;

export function CuratorView() {
  const q = useLiveCurator();
  const [filter, setFilter] = useState<(typeof FILTERS)[number][0]>("all");
  const d = q.data;
  const rows = useMemo(() => {
    const all = d?.markets ?? [];
    if (filter === "act")
      return all.filter(
        (r) => r.recommendation === "reduce_cap" || r.recommendation === "do_not_increase",
      );
    if (filter === "watch") return all.filter((r) => r.recommendation === "watch");
    if (filter === "survives") return all.filter((r) => r.recommendation === "survives");
    return all;
  }, [d, filter]);
  const sample = d?.markets.find((r) => r.tonight)?.tonight;
  const count = (k: Rec) => d?.summary[k]?.markets ?? 0;
  return (
    <div className="mx-auto max-w-[1440px] px-4 pb-24 sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Which LLTV survives tonight?</h1>
      <div className="mt-3">
        <LiveLabel block={d?.block} />
      </div>
      <p className="mt-4 max-w-[70ch] text-[18px]">
        For curators of Stock Token lending markets. Every USDG Morpho market lending against a
        Stock Token on {d?.network ?? "Robinhood Chain"}: tonight&apos;s bad case against the
        market&apos;s cushion, the highest loan-to-value that survives it, how much lenders could
        withdraw, and what to do with the cap. Read-only: nothing here sends a transaction.
      </p>
      {d && (
        <p className="mt-2 max-w-[70ch] text-[16px] font-semibold">
          {d.totals.markets} markets, {usd(d.totals.borrowed_usdg)} of {usd(d.totals.supplied_usdg)}{" "}
          USDG lent ({formatPct(d.totals.utilization)}). Cut the cap: {count("reduce_cap")}. Do not
          increase: {count("do_not_increase")}. Watch: {count("watch")}. Survives the modelled bad
          case: {count("survives")}. Read at <ZonedTime iso={d.as_of} />.
        </p>
      )}
      <div role="group" aria-label="Filter" className="mt-6 flex flex-wrap gap-2">
        {FILTERS.map(([k, label]) => (
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
          Reading every Stock Token lending market on mainnet.
        </p>
      )}
      {d && (
        <ul className="mt-6 flex flex-col md:hidden" aria-label="Markets">
          {rows.map((r) => (
            <li
              key={r.market_id}
              data-testid="curator-card"
              className="flex flex-col gap-3 border-b-[1.25px] border-rule py-4"
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className="font-display text-[24px]">{r.symbol}</span>
                <span className="text-[14px] font-semibold">LLTV {formatPct(r.lltv)}</span>
              </span>
              <CushionBar r={r} />
              <span className="flex flex-wrap gap-x-8 gap-y-2">
                <span className="flex flex-col">
                  <span className="text-[14px]">LLTV that survives</span>
                  <Survives r={r} />
                </span>
                <Liquidity r={r} />
              </span>
              <Recommendation r={r} />
            </li>
          ))}
          {rows.length === 0 && <li className="mt-4">No market matches this filter right now.</li>}
        </ul>
      )}
      {d && (
        <div className="mt-6 hidden overflow-x-auto md:block">
          <table className="w-full min-w-[880px] border-collapse text-left">
            <caption className="sr-only">
              Stock Token lending markets: tonight&apos;s bad case against each cushion
            </caption>
            <thead>
              <tr className="text-[14px]">
                {[
                  "Market",
                  "Tonight's bad case against the cushion",
                  "LLTV that survives",
                  "Lent and exit liquidity",
                  "Recommendation",
                ].map((h) => (
                  <th key={h} className="border-b-[1.25px] border-rule py-2 pr-4 font-semibold">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.market_id} data-testid="curator-row" className="align-top">
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <span className="flex flex-col">
                      <span className="font-display text-[24px]">{r.symbol}</span>
                      <span className="text-[14px] font-semibold">LLTV {formatPct(r.lltv)}</span>
                      <span className="text-[14px]" title={r.market_id}>
                        {r.market_id.slice(0, 10)}
                      </span>
                      <span className="text-[14px]">
                        Feed: {r.oracle.regime_label ?? r.oracle.state ?? "no reading"}
                        {r.oracle.quality != null ? `, quality ${r.oracle.quality}` : ""}
                      </span>
                    </span>
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <CushionBar r={r} />
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <Survives r={r} />
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <Liquidity r={r} />
                  </td>
                  <td className="border-b-[1.25px] border-rule py-3 pr-4">
                    <Recommendation r={r} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="mt-4">No market matches this filter right now.</p>}
        </div>
      )}
      <p className="mt-6 max-w-[70ch] text-[14px]">
        Cushion: how far the price can fall before a loan at the limit leaves bad debt (1 minus LLTV
        minus Morpho&apos;s liquidation incentive). The thin line on each bar is the margin
        Afterhours&apos; own vault keeps ({d ? formatPct(d.policy.margin_fraction, 0) : "a share"}{" "}
        of the cushion): past it, do not increase the cap. Watch means the bad case fits but lenders
        can barely withdraw ({d ? formatPct(d.policy.watch_utilization, 0) : "almost all"} lent or
        more), one borrower holds most of the debt. Feed state and price quality are shown but do
        not change the call. The bad case is a model:
        {sample ? ` ${coverageText(sample)}.` : " it targets 1% of closed periods."} It is not
        adjusted for the price regime and is not financial advice. Method:
        engine/afterhours/live/curator.py.
      </p>
    </div>
  );
}
