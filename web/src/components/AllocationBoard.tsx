"use client";

/**
 * AllocationBoard (docs/DESIGN.md section 6): one row per stock, weekday and weekend slots,
 * brass bars sized by the vault's USDG, the lent-out part hatched, idle as its own reservoir.
 * Bars move only because money moved: widths come from /v1/vault and glide when it changes.
 */
import { RETRY_TEXT } from "@/lib/api";
import { useEffect, useState } from "react";

import type { Market, Risk, Vault } from "@/lib/api";
import { useLiveEvent, useRisk, useVault } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

const HATCH =
  "repeating-linear-gradient(135deg, color-mix(in oklab, var(--c-on-brass) 38%, transparent) 0 2px, transparent 2px 7px)";

function Slot({
  market,
  limit,
  delay,
  routed,
}: {
  market: Market | undefined;
  limit: number;
  delay: number;
  routed: boolean;
}) {
  const supply = market?.vault_supply ?? 0;
  const lent = market?.lent_out ?? 0;
  const w = limit > 0 ? Math.min(1, supply / limit) : 0;
  const lw = limit > 0 ? Math.min(1, lent / limit) : 0;
  return (
    <div>
      <div
        className="relative h-7 overflow-hidden rounded-[6px] border-[1.25px] border-rule bg-bg"
        role="img"
        aria-label={`${formatUsd(supply)} USDG supplied, ${formatUsd(lent)} lent out`}
      >
        <div
          className="absolute inset-y-0 left-0 bg-brass"
          style={{ width: `${w * 100}%`, transition: `width 400ms var(--ease-ui) ${delay}ms` }}
        />
        <div
          className="absolute inset-y-0 left-0"
          style={{
            width: `${lw * 100}%`,
            backgroundImage: HATCH,
            transition: `width 400ms var(--ease-ui) ${delay}ms`,
          }}
        />
      </div>
      <p className="mt-1 text-[14px]">
        {supply > 0.5 ? `${formatUsd(supply)} USDG, ${formatUsd(lent)} lent` : "Empty"}
        {routed && <span className="ml-2 font-semibold">Deposits and withdrawals route here</span>}
      </p>
    </div>
  );
}

function RiskNote({ risk }: { risk: Risk["stocks"][number] | undefined }) {
  if (!risk) return null;
  const weekday = risk.tiers.weekday;
  return (
    <p className="text-[14px]">
      Bad case {formatPct(risk.worst_in_lookahead.bad_case_drop)} (
      {risk.worst_in_lookahead.period.segment}){" "}
      <span
        className="font-semibold"
        style={{ color: weekday?.allowed ? "var(--c-safe)" : "var(--c-risk)" }}
      >
        {weekday?.allowed ? "Weekday tier open" : "Weekday tier closed"}
      </span>
    </p>
  );
}

/** Flash a row briefly when a transaction for its stock confirms. */
function useFlash(): string | null {
  const { last } = useLiveEvent();
  const [flash, setFlash] = useState<string | null>(null);
  useEffect(() => {
    if (last?.type !== "tx_confirmed") return;
    const symbol = (last.data as { symbol?: string } | null)?.symbol ?? null;
    const on = window.setTimeout(() => setFlash(symbol), 0);
    const off = window.setTimeout(() => setFlash(null), 1600);
    return () => {
      window.clearTimeout(on);
      window.clearTimeout(off);
    };
  }, [last]);
  return flash;
}

export function AllocationBoard() {
  const vault = useVault();
  const risk = useRisk();
  const flash = useFlash();
  if (vault.isError) return <p role="alert">Can&apos;t reach the vault. {RETRY_TEXT}</p>;
  if (!vault.data) return <p aria-busy="true">Reading the vault onchain.</p>;
  const v: Vault = vault.data;
  const limit = v.max_share_per_stock * v.tvl_usdg;
  const symbols = Array.from(new Set(v.markets.map((m) => m.symbol)));
  const find = (s: string, t: "weekday" | "weekend") =>
    v.markets.find((m) => m.symbol === s && m.tier === t);
  const riskOf = (s: string) => risk.data?.stocks.find((r) => r.symbol === s);
  const reserve = v.idle_reserve_share * v.tvl_usdg;
  return (
    <section aria-labelledby="board-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="board-title" className="text-[36px]">
          Allocation board
        </h2>
        <p className="text-[14px]">Hatched: lent to borrowers, cannot move until repaid.</p>
      </div>
      <div className="mt-4 hidden grid-cols-[10rem_1fr_1fr] gap-6 border-b-[1.25px] border-rule pb-2 text-[14px] font-semibold md:grid">
        <span>Stock</span>
        <span>
          Weekday tier: {formatPct(v.tiers.weekday.lltv)} LTV, {formatPct(v.tiers.weekday.cushion)}{" "}
          cushion
        </span>
        <span>
          Weekend tier: {formatPct(v.tiers.weekend.lltv)} LTV, {formatPct(v.tiers.weekend.cushion)}{" "}
          cushion
        </span>
      </div>
      <ul>
        {symbols.map((s, i) => (
          <li
            key={s}
            className="grid gap-3 border-b-[1.25px] border-rule py-4 md:grid-cols-[10rem_1fr_1fr] md:gap-6"
            style={{
              outline: flash === s ? "2px solid var(--c-brass)" : "2px solid transparent",
              outlineOffset: "4px",
              transition: "outline-color 400ms var(--ease-ui)",
            }}
          >
            <div>
              <p className="font-display text-[24px] leading-none">{s}</p>
              <RiskNote risk={riskOf(s)} />
            </div>
            <div>
              <p className="mb-1 text-[14px] font-semibold md:hidden">Weekday tier</p>
              <Slot
                market={find(s, "weekday")}
                limit={limit}
                delay={i * 120}
                routed={v.liquidity_market === `${s}:weekday`}
              />
            </div>
            <div>
              <p className="mb-1 text-[14px] font-semibold md:hidden">Weekend tier</p>
              <Slot
                market={find(s, "weekend")}
                limit={limit}
                delay={i * 120 + 60}
                routed={v.liquidity_market === `${s}:weekend`}
              />
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-6">
        <p className="text-[16px] font-semibold">Idle reservoir</p>
        <div
          className="relative mt-2 h-7 overflow-hidden rounded-[6px] border-[1.25px] border-rule bg-bg"
          role="img"
          aria-label={`${formatUsd(v.idle_usdg)} USDG idle of ${formatUsd(v.tvl_usdg)}`}
        >
          <div
            className="absolute inset-y-0 left-0 bg-safe"
            style={{
              width: `${(v.idle_usdg / Math.max(v.tvl_usdg, 1)) * 100}%`,
              transition: "width 400ms var(--ease-ui)",
            }}
          />
          <div
            aria-hidden="true"
            className="absolute inset-y-[-4px] border-l-[2px] border-ink"
            style={{ left: `${v.idle_reserve_share * 100}%` }}
          />
        </div>
        <p className="mt-1 text-[14px]">
          {formatUsd(v.idle_usdg)} USDG idle; the line marks the{" "}
          {formatPct(v.idle_reserve_share, 0)} kept for withdrawals ({formatUsd(reserve)} USDG).
        </p>
      </div>
    </section>
  );
}
