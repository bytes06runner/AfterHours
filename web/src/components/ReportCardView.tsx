"use client";

/**
 * Report card (docs/DESIGN.md section 7): plain and trustworthy. Every number comes from
 * /v1/report-card, which serves artifacts/model, artifacts/backtest and artifacts/gaps. If the
 * model fell back to a baseline, the first sentence says so (it is the artifact's own sentence).
 */
import { CalibrationPlot } from "@/charts/CalibrationPlot";
import { TailChart } from "@/charts/TailChart";
import { FrontierChart } from "@/charts/FrontierChart";
import { SEGMENT_KEYS, type DecisionUniverse, type ReportCard, RETRY_TEXT } from "@/lib/api";
import { FORECASTERS } from "@/lib/names";
import { useReportCard } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

const SEGMENT_NAMES: Record<string, string> = {
  overall: "All closed periods",
  earnings: "Earnings nights",
  holiday: "Holidays",
  weekend: "Weekends",
  overnight: "Ordinary nights",
};

function Pass({ ok }: { ok: boolean }) {
  return (
    <span className="font-semibold" style={{ color: ok ? "var(--c-safe)" : "var(--c-risk)" }}>
      {ok ? "Pass" : "Miss"}
    </span>
  );
}

function Table({ caption, children }: { caption: string; children: React.ReactNode }) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-left text-[16px]">
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  );
}
const th = "border-b-[1.25px] border-rule py-2 pr-4 text-[14px] font-semibold align-bottom";
const td = "border-b-[1.25px] border-rule py-2 pr-4 align-top";

function Acceptance({ rc }: { rc: ReportCard }) {
  const a = rc.model.acceptance;
  const rows = [
    {
      name: "Coverage, all closed periods",
      detail: `missed ${formatPct(a.coverage_overall.miss_rate, 2)}, target ${formatPct(a.coverage_overall.target, 0)} within ${formatPct(a.coverage_overall.tolerance, 0)}`,
      ok: a.coverage_overall.pass,
    },
    {
      name: "Coverage, earnings nights",
      detail: `missed ${formatPct(a.coverage_earnings.miss_rate, 2)}, target ${formatPct(a.coverage_earnings.target, 0)} within ${formatPct(a.coverage_earnings.tolerance, 0)}`,
      ok: a.coverage_earnings.pass,
    },
    ...Object.entries(a.pinball_vs_baselines).map(([k, v]) => ({
      name: `Pinball loss beats ${FORECASTERS[k] ?? k}`,
      detail: `${v.model.toExponential(2)} vs ${v.baseline.toExponential(2)}`,
      ok: v.pass,
    })),
  ];
  return (
    <Table caption="Acceptance criteria for the LightGBM model">
      <thead>
        <tr>
          <th className={th}>LightGBM model criterion</th>
          <th className={th}>Held-out result</th>
          <th className={th}>Result</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.name}>
            <td className={td}>{r.name}</td>
            <td className={td}>{r.detail}</td>
            <td className={td}>
              <Pass ok={r.ok} />
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Coverage({ rc }: { rc: ReportCard }) {
  const held = rc.model.acceptance.held_out;
  const names = Object.keys(held);
  const shipped = rc.model.acceptance.shipped;
  return (
    <Table caption="Held-out miss rate and pinball loss by forecaster and kind of closed period">
      <thead>
        <tr>
          <th className={th}>Closed periods</th>
          {names.map((n) => (
            <th key={n} className={th}>
              {FORECASTERS[n] ?? n}
              {n === shipped ? " (shipped)" : ""}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {SEGMENT_KEYS.map((s) => (
          <tr key={s}>
            <td className={td}>
              {SEGMENT_NAMES[s]}
              <span className="block text-[14px]">
                {held[names[0]]?.[s]?.n.toLocaleString("en-US")} held out
              </span>
            </td>
            {names.map((n) => {
              const p = held[n]?.[s];
              return (
                <td key={n} className={td} style={n === shipped ? { fontWeight: 700 } : undefined}>
                  {p ? formatPct(p.miss_rate, 2) : "n/a"}
                  <span className="block text-[14px] font-normal">
                    pinball {p ? p.pinball.toExponential(2) : "n/a"}
                  </span>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

type DecisionData = ReportCard["decision"];

const ROWS: { key: "b" | "nearest_blend" | "fixed_map" | "dynamic"; label: string }[] = [
  { key: "b", label: "Afterhours (B): yearly tier map plus pullback" },
  { key: "nearest_blend", label: "Static blend nearest B's yield" },
  { key: "fixed_map", label: "No-hindsight fixed map" },
  { key: "dynamic", label: "Dynamic strategy (documented alternative)" },
];

function DecisionTable({ u, name }: { u: DecisionUniverse; name: string }) {
  const blends = [...u.blends].sort((a, b) => a.w - b.w);
  const rows = [
    ...ROWS.map((r) => ({
      label:
        r.key === "nearest_blend"
          ? `${r.label} (${formatPct(u.nearest_blend.w, 0)} weekday)`
          : r.label,
      p: u[r.key],
      strong: r.key === "b",
    })),
    { label: "Always weekday tier", p: blends[blends.length - 1], strong: false },
    { label: "Always weekend tier", p: blends[0], strong: false },
  ];
  return (
    <Table caption={`Held-out results, ${name}`}>
      <thead>
        <tr>
          <th className={th}>Strategy</th>
          <th className={th}>Lender yield</th>
          <th className={th}>Bad debt (USDG)</th>
          <th className={th}>Worst single night</th>
          <th className={th}>Interest (USDG)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label} style={r.strong ? { fontWeight: 700 } : undefined}>
            <td className={td}>{r.label}</td>
            <td className={td}>{formatPct(r.p.yield, 2)}</td>
            <td className={td}>{formatUsd(r.p.bad_debt)}</td>
            <td className={td}>{formatPct(r.p.worst, 3)} of the vault</td>
            <td className={td}>{formatUsd(r.p.interest)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** Plain statements of fact about B, computed from the numbers (no adjectives chosen here). */
function Facts({ d, u }: { d: DecisionData; u: DecisionUniverse }) {
  const cmp = (a: number, b: number, more: string, less: string) =>
    a > b ? more : a < b ? less : "the same";
  const b = u.b;
  const bl = u.nearest_blend;
  const fm = u.fixed_map;
  return (
    <ul className="mt-4 flex max-w-[72ch] list-disc flex-col gap-2 pl-5 text-[16px]">
      <li>
        B against the static blend nearest its yield ({formatPct(bl.w, 0)} weekday): yield{" "}
        {formatPct(b.yield, 2)} vs {formatPct(bl.yield, 2)}, bad debt {formatUsd(b.bad_debt)} vs{" "}
        {formatUsd(bl.bad_debt)} USDG, worst single night {formatPct(b.worst, 3)} vs{" "}
        {formatPct(bl.worst, 3)} of the vault.
      </li>
      <li>
        B against the no-hindsight fixed map: yield {formatPct(b.yield, 2)} vs{" "}
        {formatPct(fm.yield, 2)} ({cmp(b.yield, fm.yield, "higher", "lower")}), bad debt{" "}
        {formatUsd(b.bad_debt)} vs {formatUsd(fm.bad_debt)} USDG, worst single night{" "}
        {formatPct(b.worst, 3)} vs {formatPct(fm.worst, 3)}.
      </li>
      <li>
        The fixed map broke the {formatPct(d.cap, 2)} worst-night cap in tuning (its smallest worst
        night across all settings was {formatPct(u.fixed_map_tuning_smallest_worst, 3)}) and out of
        sample ({formatPct(fm.worst, 3)}).
      </li>
      <li>
        B broke the same cap in tuning too: {u.b_settings_meeting_cap} of {u.b_settings} settings
        met it; the rule&apos;s fallback chose the smallest worst night (
        {formatPct(u.b_tuning_worst, 3)}). Out of sample B&apos;s worst night was{" "}
        {formatPct(b.worst, 3)} ({b.worst > d.cap ? "above" : "within"} the cap).
      </li>
      <li>
        The dynamic strategy, measured and kept as an alternative: yield{" "}
        {formatPct(u.dynamic.yield, 2)}, bad debt {formatUsd(u.dynamic.bad_debt)} USDG, worst single
        night {formatPct(u.dynamic.worst, 3)}, interest {formatUsd(u.dynamic.interest)} USDG against
        the fixed map&apos;s {formatUsd(fm.interest)}.
      </li>
    </ul>
  );
}

function Pulls({ u, name }: { u: DecisionUniverse; name: string }) {
  const years = Object.entries(u.pulls.per_year).sort(([a], [b]) => a.localeCompare(b));
  const top = Object.entries(u.pulls.by_symbol)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([s, n]) => `${s} ${n}`);
  return (
    <div>
      <Table caption={`Nights B pulled unborrowed money, ${name}`}>
        <thead>
          <tr>
            <th className={th}>Year</th>
            <th className={th}>Nights with a pull</th>
            <th className={th}>USDG moved to idle</th>
          </tr>
        </thead>
        <tbody>
          {years.map(([y, v]) => (
            <tr key={y}>
              <td className={td}>{y}</td>
              <td className={td}>{v.nights}</td>
              <td className={td}>{formatUsd(v.usdg_moved)}</td>
            </tr>
          ))}
          <tr style={{ fontWeight: 700 }}>
            <td className={td}>All</td>
            <td className={td}>
              {u.pulls.total.nights} ({u.pulls.total.stock_nights} stock-nights)
            </td>
            <td className={td}>{formatUsd(u.pulls.total.usdg_moved)}</td>
          </tr>
        </tbody>
      </Table>
      <p className="mt-2 text-[14px]">
        A night counts when the pullback fired for a stock that held unborrowed vault money. Most
        pulls: {top.join(", ")} (stock-nights). Money returns when the forecast allows, so the same
        USDG can be pulled many times.
      </p>
    </div>
  );
}

function Decision({ d }: { d: DecisionData }) {
  const [u5, u35] = [d.universes.vault, d.universes.stock_tokens];
  const apy = Object.entries(d.assumed_apy).map(([k, v]) => `${k} ${formatPct(v, 1)}`);
  return (
    <section aria-labelledby="decision" className="mt-12">
      <h2 id="decision" className="text-[36px]">
        Which policy ships, and why
      </h2>
      <p className="mt-2">
        Before running, we wrote down this rule: tune on {d.tuning_years}, evaluate once on{" "}
        {d.evaluation_years}.
      </p>
      <blockquote className="mt-3 border-l-[3px] border-brass pl-4 text-[18px]">
        {d.rule}
      </blockquote>
      <p className="mt-3">The result, as recorded:</p>
      <blockquote className="mt-3 border-l-[3px] border-brass pl-4 text-[18px] font-semibold">
        {d.result}
      </blockquote>
      <p className="mt-3 text-[16px]">
        Afterhours therefore runs option B: each January every stock is rated from the previous year
        only and may lend in the highest tier its rating allows (91.5%, 86% or 77% LLTV); on a night
        when its forecast bad case exceeds every tier&apos;s limit, the money borrowers are not
        using goes idle. B was defined after option A&apos;s held-out results were seen and its
        settings were then tuned on {d.tuning_years}, so its held-out figures below come from the{" "}
        {d.second_evaluation_note}.
      </p>
      <h3 className="mt-8 text-[24px]">
        Yield against the worst single night, {u5.stocks} vault stocks, {u5.evaluation.first} to{" "}
        {u5.evaluation.last}
      </h3>
      <div className="mt-4">
        <FrontierChart u={u5} cap={d.cap} />
      </div>
      <h3 className="mt-8 text-[24px]">The {u5.stocks} vault stocks</h3>
      <DecisionTable u={u5} name={`${u5.stocks} vault stocks`} />
      <Facts d={d} u={u5} />
      <h3 className="mt-8 text-[24px]">All {u35.stocks} Stock Token underlyings</h3>
      <DecisionTable u={u35} name={`${u35.stocks} Stock Token underlyings`} />
      <Facts d={d} u={u35} />
      <h3 className="mt-8 text-[24px]">How often B acted</h3>
      <Pulls u={u5} name={`${u5.stocks} vault stocks`} />
      <div className="mt-6">
        <Pulls u={u35} name={`${u35.stocks} Stock Token underlyings`} />
      </div>
      <h3 className="mt-8 text-[24px]">Modelled rates against today&apos;s market</h3>
      <p className="mt-2 text-[16px]">
        At Robinhood Chain block {d.market_now.block.toLocaleString("en-US")} (
        {d.market_now.block_time.slice(0, 10)}), the {d.market_now.markets} Morpho markets that take
        a Stock Token as collateral held {formatUsd(d.market_now.usdg_supplied)} USDG supplied and{" "}
        {formatUsd(d.market_now.usdg_borrowed)} borrowed ({formatPct(d.market_now.utilization, 2)}{" "}
        utilization). Lenders earned a supply APY of {formatPct(d.market_now.supply_apy, 4)}{" "}
        (supply-weighted) and borrowers paid {formatPct(d.market_now.borrow_apy, 2)}, read from each
        market&apos;s interest rate model at that block. The yields above use modelled rates.
      </p>
      <p className="mt-4 text-[16px]">
        Tier yields are assumptions, not observed rates: supply APY {apy.join(", ")} by tier. The
        gap between tiers drives how much any strategy gains by lending at higher loan-to-value;
        with a smaller spread the higher tiers are worth less. Backtests: {d.label}.
      </p>
    </section>
  );
}

export function ReportCardView() {
  const q = useReportCard();
  if (q.isError)
    return (
      <Shell>
        <p role="alert">Can&apos;t load the report card. {RETRY_TEXT}</p>
      </Shell>
    );
  if (!q.data)
    return (
      <Shell>
        <p aria-busy="true">Loading the report card.</p>
      </Shell>
    );
  const rc = q.data;
  const m = rc.model;
  const shipped = m.acceptance.shipped;
  const curves = m.calibration_curves[shipped] ?? {};
  const wf = m.config.walk_forward;
  return (
    <Shell>
      <p className="mt-4 text-[21px] font-semibold">{m.first_sentence}</p>
      <p className="mt-2 text-[16px]">
        Forecasts are judged on {m.label}. Backtests use {rc.decision.label}.
      </p>

      <Decision d={rc.decision} />

      <section aria-labelledby="accept" className="mt-12">
        <h2 id="accept" className="text-[36px]">
          Acceptance
        </h2>
        <p className="mt-2">
          The LightGBM model had to pass all of these to ship.{" "}
          {m.acceptance.passed
            ? "It did."
            : `It did not, so the forecaster below is ${FORECASTERS[shipped] ?? shipped}.`}
        </p>
        <Acceptance rc={rc} />
        {m.variants_tried.length > 0 && (
          <p className="mt-4 text-[16px]">
            Variants of the model we also tried, all short of acceptance:{" "}
            {m.variants_tried
              .map(
                (v) =>
                  `target scaling ${v.target_scaling} with conformal normalisation ${v.conformal_normalize} (missed ${formatPct(v.miss_rate_overall, 2)}, pinball ${v.model_pinball.toExponential(2)})`,
              )
              .join("; ")}
            .
          </p>
        )}
      </section>

      <section aria-labelledby="calib" className="mt-12">
        <h2 id="calib" className="text-[36px]">
          Calibration of the shipped forecaster
        </h2>
        <p className="mt-2">
          Each point is a target miss rate against the share of held-out closed periods where the
          drop was worse than forecast. On the diagonal is perfect calibration.
        </p>
        <div className="mt-6 grid grid-cols-2 gap-6 md:grid-cols-3 xl:grid-cols-5">
          {SEGMENT_KEYS.filter((s) => curves[s]).map((s) => (
            <CalibrationPlot key={s} points={curves[s]} title={SEGMENT_NAMES[s]} />
          ))}
        </div>
      </section>

      <section aria-labelledby="cov" className="mt-12">
        <h2 id="cov" className="text-[36px]">
          Coverage and pinball loss
        </h2>
        <p className="mt-2">
          Share of held-out closed periods where the real drop was worse than the forecast bad case,
          at a {formatPct(m.acceptance.alpha, 0)} target. Lower pinball loss is better.
        </p>
        <Coverage rc={rc} />
      </section>

      <section aria-labelledby="tail" className="mt-12">
        <h2 id="tail" className="text-[36px]">
          How often prices gap down
        </h2>
        <p className="mt-2">
          Share of closed periods from {rc.gaps.period.first_close} to {rc.gaps.period.last_open}{" "}
          where a stock opened at least this far below its last close, across{" "}
          {rc.gaps.tickers.universe} US stocks and funds.
        </p>
        <div className="mt-4">
          <TailChart drops={rc.gaps.tail.drops} series={rc.gaps.tail.universe} />
        </div>
      </section>

      <section aria-labelledby="methods" className="mt-12">
        <h2 id="methods" className="text-[36px]">
          Methods
        </h2>
        <ul className="mt-4 flex max-w-[68ch] list-disc flex-col gap-3 pl-5">
          <li>
            A gap is the next open divided by the last close, minus one, for each closed period:
            ordinary nights, weekends, holidays and earnings nights.
          </li>
          <li>
            The forecast is the bad-case drop: the {formatPct(m.config.target_alpha, 0)} lower
            quantile of the gap for the coming closed period.
          </li>
          <li>
            Walk-forward evaluation over {m.folds} folds: {wf.train_years} years to train,{" "}
            {wf.calibrate_years} to calibrate, the next {wf.test_years} held out. No held-out year
            is ever used to fit anything.
          </li>
          <li>
            The EWMA forecaster scales each stock&apos;s daily volatility (lambda{" "}
            {m.config.baselines.ewma_lambda}) by the square root of hours closed over 24 and takes
            the normal quantile. A {m.config.conformal.method.toUpperCase()} correction per kind of
            closed period ({m.config.conformal.mondrian_segments.join(", ")}) is fitted on the
            calibration year.
          </li>
          <li>
            A tier&apos;s cushion is 1 minus LLTV minus the liquidation incentive allowance: how far
            the price can fall before a loan at the limit leaves bad debt.
          </li>
          <li>
            The shipped policy (B) rates each stock every January by its worst 1% closed-period gap
            over the previous 365 days and lets it use the highest tier whose cushion, less{" "}
            {formatPct(rc.decision.universes.vault.b_chosen.map_fraction, 0)} of it, covers that
            rating. Before each close it pulls the stock&apos;s unborrowed money when the worst
            forecast bad case over the next {rc.decision.universes.vault.b_chosen.lookahead} closed
            periods exceeds every tier&apos;s cushion less{" "}
            {formatPct(rc.decision.universes.vault.b_chosen.pullback_fraction, 0)}.
          </li>
          <li>
            Model version {m.model_version}, code version {m.code_version}.
          </li>
        </ul>
      </section>
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-[1280px] px-4 pb-24 sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Report card</h1>
      {children}
    </div>
  );
}
