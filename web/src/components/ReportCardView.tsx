"use client";

/**
 * Report card (docs/DESIGN.md section 7): plain and trustworthy. Every number comes from
 * /v1/report-card, which serves artifacts/model, artifacts/backtest and artifacts/gaps. If the
 * model fell back to a baseline, the first sentence says so (it is the artifact's own sentence).
 */
import { CalibrationPlot } from "@/charts/CalibrationPlot";
import { TailChart } from "@/charts/TailChart";
import { SEGMENT_KEYS, STRATEGIES, type ReportCard, type StrategyKey } from "@/lib/api";
import { useReportCard } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

export const FORECASTERS: Record<string, string> = {
  model: "LightGBM quantile model",
  global_segment: "Segment quantile",
  ticker_segment: "Stock and segment quantile",
  ewma_normal: "EWMA volatility",
};
export const STRATEGY_NAMES: Record<StrategyKey, string> = {
  always_weekday: "Always weekday tier",
  always_weekend: "Always weekend tier",
  afterhours: "Afterhours",
  perfect_foresight: "Perfect foresight",
};
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

function Strategies({ rc }: { rc: ReportCard }) {
  const s = rc.backtest.strategies;
  const rows: { label: string; value: (k: StrategyKey) => string }[] = [
    {
      label: "Net lender yield, annualised",
      value: (k) => formatPct(s[k].net_lender_yield_annualised, 2),
    },
    { label: "Bad debt", value: (k) => `${formatUsd(s[k].bad_debt_usdg)} USDG` },
    { label: "Closed periods with bad debt", value: (k) => String(s[k].bad_debt_events) },
    {
      label: "Worst single event",
      value: (k) => {
        const w = s[k].worst_event;
        return w?.bad_debt_usdg !== undefined && w.share_of_vault !== undefined
          ? `${formatUsd(w.bad_debt_usdg)} USDG (${formatPct(w.share_of_vault, 2)} of the vault), ${w.ticker} ${w.session_prev}`
          : "None";
      },
    },
    {
      label: "Time in weekday / weekend / idle",
      value: (k) =>
        `${formatPct(s[k].share_of_time.weekday, 0)} / ${formatPct(s[k].share_of_time.weekend, 0)} / ${formatPct(s[k].share_of_time.idle, 0)}`,
    },
    { label: "Reallocations", value: (k) => s[k].reallocations.toLocaleString("en-US") },
  ];
  return (
    <Table caption="Backtest results for the four strategies">
      <thead>
        <tr>
          <th className={th}>
            <span className="sr-only">Measure</span>
          </th>
          {STRATEGIES.map((k) => (
            <th key={k} className={th}>
              {STRATEGY_NAMES[k]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.label}>
            <td className={`${td} font-semibold`}>{r.label}</td>
            {STRATEGIES.map((k) => (
              <td
                key={k}
                className={td}
                style={k === "afterhours" ? { fontWeight: 700 } : undefined}
              >
                {r.value(k)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function Sensitivity({ rc }: { rc: ReportCard }) {
  const label = (kind: string, v: number) =>
    kind === "rate_spread"
      ? `Weekday rate premium x${v}`
      : kind === "loan_turnover"
        ? `Loan turnover ${formatPct(v, 0)} per session`
        : `${kind} ${v}`;
  return (
    <Table caption="Sensitivity of yield and bad debt to the rate and borrower assumptions">
      <thead>
        <tr>
          <th className={th}>Assumption</th>
          {STRATEGIES.map((k) => (
            <th key={k} className={th}>
              {STRATEGY_NAMES[k]}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rc.backtest.sensitivity.map((row) => (
          <tr key={`${row.kind}-${row.value}`}>
            <td className={td}>{label(row.kind, row.value)}</td>
            {STRATEGIES.map((k) => {
              const r = row.results[k];
              return (
                <td
                  key={k}
                  className={td}
                  style={k === "afterhours" ? { fontWeight: 700 } : undefined}
                >
                  {r ? formatPct(r.net_lender_yield_annualised, 2) : "n/a"}
                  <span className="block text-[14px] font-normal">
                    {r ? `${formatUsd(r.bad_debt_usdg)} bad debt` : ""}
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

export function ReportCardView() {
  const q = useReportCard();
  if (q.isError)
    return (
      <Shell>
        <p role="alert">Can&apos;t load the report card. Retrying shortly.</p>
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
  const bt = rc.backtest;
  return (
    <Shell>
      <p className="mt-4 text-[21px] font-semibold">{m.first_sentence}</p>
      <p className="mt-2 text-[16px]">
        Forecasts are judged on {m.label}. The backtest uses {bt.label}.
      </p>

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

      <section aria-labelledby="bt" className="mt-12">
        <h2 id="bt" className="text-[36px]">
          Backtest: four ways to run the vault
        </h2>
        <p className="mt-2">
          {formatUsd(bt.assumptions.vault_usdg)} USDG across {bt.selected.join(", ")}, from{" "}
          {bt.period.first} to {bt.period.last}: {bt.period.closed_periods.toLocaleString("en-US")}{" "}
          closed periods. Historical stock prices, simulated vault. Perfect foresight knows every
          gap in advance and is not achievable; it marks the ceiling.
        </p>
        <Strategies rc={rc} />
        <p className="mt-4 text-[16px]">
          Afterhours settings: weekday tier LLTV {formatPct(bt.chosen.weekday_lltv)}, weekend tier
          LLTV {formatPct(bt.chosen.weekend_lltv)}, safety margin{" "}
          {formatPct(bt.chosen.safety_margin, 0)}, looking {bt.chosen.lookahead_closed_periods}{" "}
          closed periods ahead. Chosen by this rule: {bt.chosen.rule} ({bt.chosen.eligible_settings}{" "}
          settings qualified).
        </p>
        <h3 className="mt-8 text-[24px]">Sensitivity</h3>
        <p className="mt-2">
          Supply rates, utilisation and borrower behaviour are assumptions set in config. These rows
          rerun the backtest with them changed.
        </p>
        <Sensitivity rc={rc} />
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
            A tier is open for a stock only if its bad-case drop plus the safety margin fits inside
            the tier&apos;s cushion: 1 minus LLTV minus the liquidation incentive allowance.
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
