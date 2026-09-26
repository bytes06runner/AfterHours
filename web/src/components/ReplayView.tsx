"use client";

/**
 * Replay (docs/DESIGN.md section 7): a theatre for one historical closed period. The scenario
 * picker lists the backtest's scenarios; two stages, "Ordinary vault" (always in the weekday
 * tier) and "Afterhours", share one scrubbable timeline over the real price path. Everything
 * comes from /v1/replay, which serves artifacts/backtest/replay. Historical stock prices,
 * simulated vault.
 */
import { RETRY_TEXT } from "@/lib/api";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

import { ReplayPriceChart } from "@/charts/ReplayPriceChart";
import type { Replay, ReplayPoint, Scenario } from "@/lib/api";
import { useReplay, useScenarios } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

import { TornEdge } from "@/art/TornEdge";

import { SplitFlap } from "./SplitFlap";

const SEGMENT: Record<string, string> = {
  earnings: "Earnings night",
  weekend: "Weekend",
  holiday: "Holiday",
  overnight: "Overnight",
};
const HATCH =
  "repeating-linear-gradient(135deg, color-mix(in oklab, var(--c-on-brass) 38%, transparent) 0 2px, transparent 2px 7px)";

function day(iso: string): string {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

/** "24.5% below" or "26.1% above" the previous close. */
function gapWords(g: number): string {
  return `${formatPct(Math.abs(g))} ${g < 0 ? "below" : "above"}`;
}

function Bar({
  label,
  supply,
  lent,
  scale,
}: {
  label: string;
  supply: number;
  lent: number;
  scale: number;
}) {
  return (
    <div>
      <p className="text-[14px] font-semibold">{label}</p>
      <div
        className="relative mt-1 h-6 overflow-hidden rounded-[6px] border-[1.25px] border-rule bg-bg"
        role="img"
        aria-label={`${label}: ${formatUsd(supply)} USDG supplied, ${formatUsd(lent)} lent out`}
      >
        <div
          className="absolute inset-y-0 left-0 bg-brass"
          style={{ width: `${(supply / scale) * 100}%`, transition: "width 400ms var(--ease-ui)" }}
        />
        <div
          className="absolute inset-y-0 left-0"
          style={{
            width: `${(lent / scale) * 100}%`,
            backgroundImage: HATCH,
            transition: "width 400ms var(--ease-ui)",
          }}
        />
      </div>
      <p className="mt-1 text-[14px]">
        {supply > 0.5 ? `${formatUsd(supply)} USDG, ${formatUsd(lent)} lent` : "Empty"}
      </p>
    </div>
  );
}

function Stage({
  title,
  note,
  ticker,
  point,
  scale,
  hit,
}: {
  title: string;
  note: string;
  ticker: string;
  point: ReplayPoint;
  scale: number;
  hit: boolean;
}) {
  return (
    <section
      aria-label={title}
      className="flex flex-col gap-4 rounded-[12px] border-[1.25px] border-rule bg-surface p-5"
      style={{
        outline: hit ? "2px solid var(--c-risk)" : "2px solid transparent",
        outlineOffset: 3,
      }}
    >
      <div>
        <h3 className="text-[28px]">{title}</h3>
        <p className="text-[14px]">{note}</p>
      </div>
      <Bar
        label={`${ticker}, weekday tier`}
        supply={point.weekday_supply}
        lent={point.weekday_lent}
        scale={scale}
      />
      <Bar
        label={`${ticker}, weekend tier`}
        supply={point.weekend_supply}
        lent={point.weekend_lent}
        scale={scale}
      />
      <div className="border-t-[1.25px] border-rule pt-4">
        <p className="text-[14px] font-semibold">Bad debt so far (USDG)</p>
        <p className="mt-1 text-[36px] leading-none">
          <SplitFlap
            value={formatUsd(point.bad_debt_cum)}
            label={`${formatUsd(point.bad_debt_cum)} USDG bad debt so far`}
          />
        </p>
        <p className="mt-2 text-[14px]">
          Interest earned so far: {formatUsd(point.interest_cum)} USDG
        </p>
      </div>
    </section>
  );
}

/** The reason Afterhours would have written before this close, from the replay's own numbers. */
function Reason({ replay, index }: { replay: Replay; index: number }) {
  const p = replay.periods[index];
  const s = replay.vaults.afterhours.series;
  const now = s[index];
  const prev = index > 0 ? s[index - 1] : null;
  const margin = replay.settings.safety_margin;
  const need = p.bad_case_drop + margin;
  const wd = replay.tiers.weekday;
  const we = replay.tiers.weekend;
  const verdict = p.allowed.weekday
    ? `That fits inside the weekday tier's ${formatPct(wd.cushion)} cushion, so lending can stay at full speed.`
    : p.allowed.weekend
      ? `That is more than the weekday tier's ${formatPct(wd.cushion)} cushion but fits the weekend tier's ${formatPct(we.cushion)}, so ${replay.ticker} lends only in the weekend tier.`
      : `That is more than both cushions (weekday ${formatPct(wd.cushion)}, weekend ${formatPct(we.cushion)}), so Afterhours withdraws everything borrowers are not using.`;
  const moved = prev
    ? (["weekday", "weekend"] as const)
        .map((t) => {
          const d = now[`${t}_supply`] - prev[`${t}_supply`];
          return Math.abs(d) >= 1
            ? `${d > 0 ? "added" : "pulled"} ${formatUsd(Math.abs(d))} USDG ${d > 0 ? "to" : "from"} the ${t} tier`
            : null;
        })
        .filter(Boolean)
    : [];
  return (
    <article aria-label="Afterhours reason for this close" className="max-w-[640px]">
      <div className="rounded-t-[12px] border-x-[1.25px] border-t-[1.25px] border-rule bg-surface px-5 pb-4 pt-5">
        <header className="border-b-[1.25px] border-dashed border-rule pb-3">
          <h3 className="font-display text-[24px]">
            {replay.ticker} before the close on {day(p.session_prev)}
          </h3>
          <p className="text-[14px]">What Afterhours would have written (simulated vault)</p>
        </header>
        <p className="mt-4 text-[18px] leading-[1.5]">
          The bad case for {replay.ticker} over the next {replay.settings.lookahead_closed_periods}{" "}
          closed periods is a {formatPct(p.bad_case_drop)} drop; with the {formatPct(margin, 0)}{" "}
          safety margin that is {formatPct(need)}. {verdict}
        </p>
        <p className="mt-3 text-[16px]">
          {moved.length ? `It ${moved.join(" and ")}.` : "No money moved at this close."} What
          happened: {replay.ticker} opened {gapWords(p.g)} its close (
          {SEGMENT[p.segment] ?? p.segment}).
        </p>
      </div>
      <TornEdge />
    </article>
  );
}

function Picker({
  scenarios,
  selected,
  onSelect,
}: {
  scenarios: Scenario[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <nav aria-label="Scenarios">
      <h2 className="text-[24px]">Pick a night</h2>
      <label className="mt-3 flex flex-col gap-1 text-[14px] font-semibold lg:hidden">
        Scenario
        <select
          value={selected ?? ""}
          onChange={(e) => onSelect(e.target.value)}
          className="min-h-[48px] rounded-[10px] border-[1.25px] border-rule bg-bg px-3 text-[16px]"
        >
          {scenarios.map((s) => (
            <option key={s.id} value={s.id}>
              {s.ticker} {formatPct(s.g)}, {SEGMENT[s.segment]}, {s.session_prev}
            </option>
          ))}
        </select>
      </label>
      <ul className="mt-3 hidden flex-col lg:flex">
        {scenarios.map((s) => (
          <li key={s.id}>
            <button
              type="button"
              aria-pressed={selected === s.id}
              onClick={() => onSelect(s.id)}
              className="w-full border-b-[1.25px] border-rule py-3 text-left"
              style={
                selected === s.id
                  ? { boxShadow: "inset 4px 0 0 var(--c-brass)", paddingLeft: 12 }
                  : undefined
              }
            >
              <span className="block text-[18px] font-bold">
                {s.ticker} {formatPct(s.g)}
              </span>
              <span className="block text-[14px]">
                {SEGMENT[s.segment]}, {day(s.session_prev)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function Theatre({ replay }: { replay: Replay }) {
  const event = Math.max(
    0,
    replay.periods.findIndex((p) => p.session_prev === replay.session_prev),
  );
  const [index, setIndex] = useState(event);
  const [playing, setPlaying] = useState(false);
  const reduce = useReducedMotion();
  const last = replay.periods.length - 1;
  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => {
      setIndex((i) => {
        if (i >= last) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, 900);
    return () => window.clearInterval(t);
  }, [playing, last]);
  const scale = useMemo(
    () =>
      Math.max(
        1,
        ...Object.values(replay.vaults).flatMap((v) =>
          v.series.map((p) => Math.max(p.weekday_supply, p.weekend_supply)),
        ),
      ),
    [replay],
  );
  const p = replay.periods[index];
  const ordinary = replay.vaults.always_weekday.series[index];
  const ah = replay.vaults.afterhours.series[index];
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <div>
        <h2 className="text-[36px]">
          {replay.ticker}, {SEGMENT[replay.segment]?.toLowerCase()} of {day(replay.session_prev)}
        </h2>
        <p className="mt-1 text-[16px]">
          Opened {gapWords(replay.g)} the previous close after {replay.hours_closed} hours closed.{" "}
          {formatUsd(replay.vault_usdg)} USDG vault. Historical stock prices, simulated vault.
        </p>
      </div>
      <ReplayPriceChart replay={replay} index={index} onSelect={setIndex} />
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn btn-brass"
          onClick={() => {
            if (reduce) {
              setIndex(event);
              return;
            }
            if (index >= last) setIndex(0);
            setPlaying((x) => !x);
          }}
        >
          {playing ? "Pause" : reduce ? "Jump to the gap" : "Replay this night"}
        </button>
        <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-[14px] font-semibold">
          Closed period {index + 1} of {last + 1}: {day(p.session_prev)} close to{" "}
          {day(p.session_next)} open
          <input
            type="range"
            min={0}
            max={last}
            value={index}
            onChange={(e) => {
              setPlaying(false);
              setIndex(Number(e.target.value));
            }}
            className="w-full accent-[var(--c-brass)]"
          />
        </label>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <Stage
          title="Ordinary vault"
          note={`Always in the weekday tier (LLTV ${formatPct(replay.tiers.weekday.lltv)})`}
          ticker={replay.ticker}
          point={ordinary}
          scale={scale}
          hit={ordinary.bad_debt_period > 0}
        />
        <Stage
          title="Afterhours"
          note={`Moves between weekday (LLTV ${formatPct(replay.tiers.weekday.lltv)}) and weekend (LLTV ${formatPct(replay.tiers.weekend.lltv)}) before each close`}
          ticker={replay.ticker}
          point={ah}
          scale={scale}
          hit={ah.bad_debt_period > 0}
        />
      </div>
      <p className="text-[14px]">
        Hatched: lent to borrowers, cannot move until repaid. Bad debt appears when a price opens
        below what borrowers owe plus the liquidation incentive.
      </p>
      <Reason replay={replay} index={index} />
    </div>
  );
}

export function ReplayView() {
  const scenarios = useScenarios();
  const [picked, setPicked] = useState<string | null>(null);
  const list = scenarios.data?.scenarios ?? [];
  // Open on the worst drop; the list keeps the backtest's order.
  const worst = list.reduce<Scenario | null>((a, b) => (a === null || b.g < a.g ? b : a), null);
  const id = picked ?? worst?.id ?? null;
  const replay = useReplay(id);
  return (
    <div className="mx-auto max-w-[1280px] px-4 pb-24 sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Replay</h1>
      <p className="mt-3 text-[18px]">
        The largest real gaps in the backtest, replayed on a simulated vault: one that always lends
        at the weekday tier, and Afterhours. Historical stock prices, simulated vault.
      </p>
      {scenarios.isError && <p role="alert">Can&apos;t load the scenarios. {RETRY_TEXT}</p>}
      <div className="mt-10 grid gap-10 lg:grid-cols-[260px_1fr]">
        {scenarios.isSuccess && list.length === 0 ? (
          <p className="lg:col-span-2">
            No replays yet. They are generated with the backtest (make report), from the largest
            gaps it finds.
          </p>
        ) : (
          <>
            {list.length > 0 ? (
              <Picker scenarios={list} selected={id} onSelect={setPicked} />
            ) : (
              <p aria-busy="true" className="min-h-[112px]">
                Loading scenarios.
              </p>
            )}
            {replay.data ? (
              <Theatre key={replay.data.id} replay={replay.data} />
            ) : replay.isError ? (
              <p role="alert">Can&apos;t load this replay. {RETRY_TEXT}</p>
            ) : (
              <p aria-busy="true">Loading the replay.</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
