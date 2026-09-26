"use client";

/**
 * Almanac (docs/DESIGN.md section 7): a paper spread with one column per upcoming day, closed
 * periods as night bands, earnings as small bells, and per stock the predicted bad-case drop as a
 * bar against each tier's allowed limit (cushion minus the safety margin). Clicking a stock opens
 * its RiskGauge and drivers. Data: /v1/almanac, /v1/risk, /v1/vault.
 */
import { RETRY_TEXT } from "@/lib/api";
import "@/art/art.css";

import { useState } from "react";

import { useWidth } from "@/charts/useWidth";
import type { Almanac, Forecast, Risk } from "@/lib/api";
import { useAlmanac, useRisk, useVault } from "@/lib/queries";
import { formatPct } from "@/lib/time";

import { RiskGauge } from "./RiskGauge";
import { DriverBars } from "./DriverBars";

const DAYS = 14;
const TZ = "America/New_York";
const SEGMENT: Record<string, string> = {
  earnings: "Earnings night",
  weekend: "Weekend",
  holiday: "Holiday",
  overnight: "Overnight",
};

type Limits = { weekday: number; weekend: number };
type Verdict = "weekday" | "weekend" | "none";

function verdict(drop: number, limits: Limits): Verdict {
  return drop <= limits.weekday ? "weekday" : drop <= limits.weekend ? "weekend" : "none";
}
const COLOR: Record<Verdict, string> = {
  weekday: "var(--c-safe)",
  weekend: "var(--c-brass)",
  none: "var(--c-risk)",
};
const VERDICT_TEXT: Record<Verdict, string> = {
  weekday: "both tiers open",
  weekend: "weekend tier only",
  none: "neither tier",
};

function nyParts(t: number) {
  const f = new Intl.DateTimeFormat("en-US", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(t));
  const get = (k: string) => Number(f.find((p) => p.type === k)?.value);
  return { y: get("year"), m: get("month"), d: get("day"), h: get("hour") };
}

/** UTC milliseconds of midnight in New York on the NY calendar day containing t, plus n days. */
function nyMidnight(t: number, n = 0): number {
  const { y, m, d } = nyParts(t);
  for (const off of [4, 5]) {
    const c = Date.UTC(y, m - 1, d + n, off);
    if (nyParts(c).h === 0) return c;
  }
  return Date.UTC(y, m - 1, d + n, 5);
}

const fmt = (t: number, o: Intl.DateTimeFormatOptions) =>
  new Intl.DateTimeFormat("en-US", { timeZone: TZ, ...o }).format(new Date(t));

function BellIcon({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x - 7} ${y})`} aria-hidden="true">
      <path
        d="M7 1 C3 1 3 5 3 8 L1 11 L13 11 L11 8 C11 5 11 1 7 1 Z"
        fill="var(--c-brass)"
        stroke="var(--c-text)"
        strokeWidth={1.25}
      />
      <circle cx={7} cy={12.5} r={1.6} fill="var(--c-text)" />
    </g>
  );
}

function Spread({
  almanac,
  limits,
  selected,
  onSelect,
}: {
  almanac: Almanac;
  limits: Limits;
  selected: string | null;
  onSelect: (s: string) => void;
}) {
  const [ref, width] = useWidth<HTMLDivElement>(1200);
  const now = Date.parse(almanac.now);
  const t0 = nyMidnight(now);
  const t1 = nyMidnight(now, DAYS);
  const label = 88;
  const W = Math.max(720, width);
  const x = (t: number) => label + ((t - t0) / (t1 - t0)) * (W - label);
  const headH = 44;
  const bandH = 34;
  const rowH = 56;
  const top = headH + bandH + 8;
  const H = top + almanac.stocks.length * rowH + 8;
  const full = Math.max(
    limits.weekend * 1.25,
    ...almanac.stocks.flatMap((s) => s.forecasts.map((f) => f.bad_case_drop)),
  );
  const days = Array.from({ length: DAYS }, (_, i) => nyMidnight(now, i));
  return (
    <div
      ref={ref}
      className="almanac-paper overflow-x-auto rounded-[12px] border-[1.25px] border-rule"
    >
      <svg
        width={W}
        height={H}
        role="img"
        aria-label={`Almanac of the next ${DAYS} days: closed periods and each stock's bad-case drop`}
      >
        {days.map((d, i) => (
          <g key={d}>
            <line x1={x(d)} x2={x(d)} y1={0} y2={H} stroke="var(--c-rule)" strokeWidth={1.25} />
            <text x={x(d) + 6} y={18} fontSize={12} fontWeight={700} fill="var(--c-text)">
              {fmt(d, { weekday: "short" })}
            </text>
            <text x={x(d) + 6} y={34} fontSize={12} fill="var(--c-text)">
              {fmt(d, { month: "short", day: "numeric" })}
            </text>
            {i === 0 && (
              <line
                x1={x(now)}
                x2={x(now)}
                y1={headH - 4}
                y2={H}
                stroke="var(--c-brass)"
                strokeWidth={2}
              />
            )}
          </g>
        ))}
        {almanac.periods.map((p) => {
          const a = Math.max(x(Date.parse(p.starts)), label);
          const b = Math.min(x(Date.parse(p.ends)), W);
          const text =
            b - a > 110 ? `${SEGMENT[p.segment]} ${p.hours} h` : b - a > 40 ? `${p.hours} h` : "";
          return (
            <g key={p.starts}>
              <rect
                x={a}
                y={headH}
                width={Math.max(0, b - a)}
                height={bandH}
                rx={4}
                className="almanac-night"
              />
              <text
                x={a + 6}
                y={headH + 22}
                fontSize={12}
                fontWeight={600}
                fill="var(--night-text)"
              >
                {text}
              </text>
            </g>
          );
        })}
        {almanac.stocks.map((s, r) => {
          const y0 = top + r * rowH;
          const inner = rowH - 14;
          // Square-root scale: small nightly drops stay visible next to an earnings night.
          const yv = (v: number) => y0 + inner - Math.sqrt(Math.min(v, full) / full) * inner;
          const isSel = selected === s.symbol;
          return (
            <g key={s.symbol}>
              <rect
                x={0}
                y={y0 - 2}
                width={W}
                height={rowH}
                fill={isSel ? "var(--c-brass)" : "transparent"}
                opacity={isSel ? 0.12 : 0}
              />
              <foreignObject x={4} y={y0 + 6} width={label - 8} height={36}>
                <button
                  type="button"
                  onClick={() => onSelect(s.symbol)}
                  aria-pressed={isSel}
                  className="font-display h-full w-full text-left text-[21px] underline decoration-brass decoration-[1.5px] underline-offset-4"
                >
                  {s.symbol}
                </button>
              </foreignObject>
              <line
                x1={label}
                x2={W}
                y1={yv(limits.weekday)}
                y2={yv(limits.weekday)}
                stroke="var(--c-safe)"
                strokeWidth={1.25}
                strokeDasharray="4 3"
              />
              <line
                x1={label}
                x2={W}
                y1={yv(limits.weekend)}
                y2={yv(limits.weekend)}
                stroke="var(--c-brass)"
                strokeWidth={1.25}
                strokeDasharray="4 3"
              />
              {s.forecasts.map((f) => {
                const a = Math.max(x(Date.parse(f.period.starts)), label) + 2;
                const b = Math.min(x(Date.parse(f.period.ends)), W) - 2;
                const v = verdict(f.bad_case_drop, limits);
                return (
                  <g
                    key={f.period.starts}
                    onClick={() => onSelect(s.symbol)}
                    style={{ cursor: "pointer" }}
                  >
                    <title>{`${s.symbol}, ${SEGMENT[f.period.segment]} from ${fmt(Date.parse(f.period.starts), { weekday: "short", hour: "numeric" })}: bad case ${formatPct(f.bad_case_drop)}, ${VERDICT_TEXT[v]}`}</title>
                    <rect
                      x={a}
                      y={yv(f.bad_case_drop)}
                      width={Math.max(2, b - a)}
                      height={y0 + inner - yv(f.bad_case_drop)}
                      fill={COLOR[v]}
                    />
                    {b - a > 34 && (
                      // Tall bars carry their label inside, so it never runs into the night band.
                      <text
                        x={a + 2}
                        y={
                          yv(f.bad_case_drop) - y0 < 12
                            ? yv(f.bad_case_drop) + 12
                            : yv(f.bad_case_drop) - 3
                        }
                        fontSize={11}
                        fontWeight={700}
                        fill={yv(f.bad_case_drop) - y0 < 12 ? "var(--c-bg)" : "var(--c-text)"}
                      >
                        {formatPct(f.bad_case_drop)}
                      </text>
                    )}
                  </g>
                );
              })}
              {s.earnings.map((e) => {
                const d = Date.parse(`${e.date}T12:00:00Z`);
                const at = nyMidnight(d) + (e.timing === "bmo" ? 9.5 : 16) * 3_600_000;
                return at >= t0 && at <= t1 ? (
                  <BellIcon key={e.date} x={x(at)} y={y0 + inner - 2} />
                ) : null;
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

/** Phones: the same facts as a list, one entry per closed period. */
function List({
  almanac,
  limits,
  onSelect,
}: {
  almanac: Almanac;
  limits: Limits;
  onSelect: (s: string) => void;
}) {
  return (
    <ol className="almanac-paper flex flex-col rounded-[12px] border-[1.25px] border-rule">
      {almanac.periods.map((p) => (
        <li key={p.starts} className="border-b-[1.25px] border-rule px-4 py-3">
          <p className="text-[16px] font-bold">
            {fmt(Date.parse(p.starts), {
              weekday: "short",
              month: "short",
              day: "numeric",
              hour: "numeric",
              minute: "2-digit",
            })}
          </p>
          <p className="text-[14px]">
            {SEGMENT[p.segment]}, closed {p.hours} hours
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {almanac.stocks.map((s) => {
              const f = s.forecasts.find((x) => x.period.starts === p.starts);
              if (!f) return null;
              const v = verdict(f.bad_case_drop, limits);
              return (
                <li key={s.symbol}>
                  <button
                    type="button"
                    onClick={() => onSelect(s.symbol)}
                    className="badge"
                    style={{ borderColor: COLOR[v] }}
                  >
                    <span
                      aria-hidden="true"
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: COLOR[v] }}
                    />
                    {s.symbol} {formatPct(f.bad_case_drop)}
                    {f.period.segment === "earnings" ? ", earnings" : ""}
                    <span className="sr-only">, {VERDICT_TEXT[v]}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </li>
      ))}
    </ol>
  );
}

function Detail({
  stock,
  risk,
  cushions,
}: {
  stock: Risk["stocks"][number];
  risk: Risk;
  cushions: Limits;
}) {
  const w: Forecast = stock.worst_in_lookahead;
  return (
    <section aria-labelledby="detail-title" className="stepped bg-surface p-6">
      <h2 id="detail-title" className="text-[36px]">
        {stock.symbol}
      </h2>
      <p className="mt-1 text-[16px]">
        Worst of the next {risk.lookahead_closed_periods} closed periods:{" "}
        {SEGMENT[w.period.segment]?.toLowerCase()} from{" "}
        {fmt(Date.parse(w.period.starts), { weekday: "long", hour: "numeric", minute: "2-digit" })}{" "}
        New York, {w.period.hours} hours closed.
      </p>
      <div className="mt-5 grid gap-8 md:grid-cols-[300px_1fr]">
        <RiskGauge drop={w.bad_case_drop} margin={risk.safety_margin} cushions={cushions} />
        <div className="flex flex-col gap-4">
          <div>
            <h3 className="text-[21px]">What made up the bad case</h3>
            <div className="mt-2">
              <DriverBars
                drivers={w.drivers.map((d) => ({
                  feature: d.feature,
                  value: d.contribution,
                  detail: d.detail,
                }))}
              />
            </div>
            <ul className="mt-2 text-[14px]">
              {w.drivers.map((d) => (
                <li key={d.feature}>{d.detail}</li>
              ))}
            </ul>
          </div>
          <div>
            <h3 className="text-[21px]">Tiers</h3>
            <ul className="mt-2 flex flex-col gap-2 text-[16px]">
              {Object.entries(stock.tiers).map(([t, v]) => (
                <li key={t}>
                  <span className="font-semibold">
                    <span
                      aria-hidden="true"
                      className="mr-2 inline-block h-3 w-3 rounded-full align-baseline"
                      style={{ background: v.allowed ? "var(--c-safe)" : "var(--c-risk)" }}
                    />
                    {t === "weekday" ? "Weekday tier" : "Weekend tier"}{" "}
                    {v.allowed ? "open" : "closed"}:
                  </span>{" "}
                  {v.reason}
                </li>
              ))}
            </ul>
          </div>
          <p className="text-[14px]">
            Forecast by {w.method}, model version {w.model_version.slice(0, 8)}, at a{" "}
            {formatPct(w.alpha, 0)} miss rate.
          </p>
        </div>
      </div>
    </section>
  );
}

export function AlmanacView() {
  const almanac = useAlmanac(DAYS);
  const risk = useRisk();
  const vault = useVault();
  const [selected, setSelected] = useState<string | null>(null);
  const tiers = vault.data?.tiers;
  const margin = risk.data?.safety_margin;
  const cushions = tiers
    ? { weekday: tiers.weekday.cushion, weekend: tiers.weekend.cushion }
    : null;
  const limits =
    cushions && margin !== undefined
      ? { weekday: cushions.weekday - margin, weekend: cushions.weekend - margin }
      : null;
  const symbol = selected ?? risk.data?.stocks[0]?.symbol ?? null;
  const stock = risk.data?.stocks.find((s) => s.symbol === symbol);
  const pick = (s: string) => {
    setSelected(s);
    requestAnimationFrame(() =>
      document.getElementById("detail-title")?.scrollIntoView({ block: "nearest" }),
    );
  };
  return (
    <div className="mx-auto max-w-[1280px] px-4 pb-24 sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Almanac</h1>
      <p className="mt-3 text-[18px]">
        The next {DAYS} days of closed markets. Each bar is a stock&apos;s forecast bad-case drop
        for one closed period, set against how far each tier can fall before lenders lose money,
        less the {margin !== undefined ? formatPct(margin, 0) : ""} safety margin.
      </p>
      <div className="min-h-[56px] md:min-h-[28px]">
        {limits && (
          <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-[14px]">
            <li className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3"
                style={{ background: COLOR.weekday }}
              />
              Under {formatPct(limits.weekday)}: both tiers open
            </li>
            <li className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3"
                style={{ background: COLOR.weekend }}
              />
              Under {formatPct(limits.weekend)}: weekend tier only
            </li>
            <li className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-3 w-3"
                style={{ background: COLOR.none }}
              />
              Above: neither tier
            </li>
            <li className="flex items-center gap-2">
              <svg width="14" height="16" aria-hidden="true">
                <BellIcon x={7} y={1} />
              </svg>
              Earnings
            </li>
          </ul>
        )}
      </div>
      <div className="mt-6 min-h-[380px]">
        {almanac.isError || vault.isError ? (
          <p role="alert">Can&apos;t load the almanac. {RETRY_TEXT}</p>
        ) : almanac.data && limits ? (
          <>
            <div className="hidden md:block">
              <Spread almanac={almanac.data} limits={limits} selected={symbol} onSelect={pick} />
            </div>
            <div className="md:hidden">
              <List almanac={almanac.data} limits={limits} onSelect={pick} />
            </div>
          </>
        ) : (
          <p aria-busy="true">Reading the calendar and forecasts.</p>
        )}
      </div>
      <div className="mt-10">
        {stock && risk.data && cushions && (
          <Detail stock={stock} risk={risk.data} cushions={cushions} />
        )}
      </div>
    </div>
  );
}
