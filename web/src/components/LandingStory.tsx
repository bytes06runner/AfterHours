"use client";

/**
 * Landing scroll story (docs/DESIGN.md section 7): the gap chart from the M2 study, the two bad
 * settings, the board at the bell, a telegram, the replay teaser and the report card numbers.
 * On wide screens the visual stays pinned while the steps scroll; GSAP ScrollTrigger is loaded
 * only here, only on wide screens, and never with reduced motion. Without it every step shows
 * its own visual inline. All numbers come from the API (artifacts and the vault).
 */
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { GapHistogram } from "@/charts/GapHistogram";
import { api, type ReportCard, type Scenario, type Vault, RETRY_TEXT } from "@/lib/api";
import { useReplay, useReportCard, useScenarios, useVault } from "@/lib/queries";
import { STRATEGY_NAMES } from "@/lib/names";
import { formatPct, formatUsd } from "@/lib/time";

// The telegram carries the verifier (hashing, chain reads); load it only when it is shown.
const Telegram = dynamic(() => import("./Telegram").then((m) => m.Telegram), {
  loading: () => <p aria-busy="true">Loading the telegram.</p>,
});

/** Share of periods in bins entirely below -threshold, and the bin edge actually used. */
function shareBelow(edges: number[], share: number[], threshold: number) {
  let edge = edges[0];
  let total = 0;
  share.forEach((s, i) => {
    if (edges[i + 1] <= -threshold + 1e-12) {
      total += s;
      edge = edges[i + 1];
    }
  });
  return { share: total, drop: -edge };
}

function GapVisual({ rc, vault }: { rc: ReportCard; vault: Vault }) {
  const h = rc.gaps.histograms.universe;
  const earn = h.segments.earnings;
  return (
    <figure>
      <GapHistogram
        edges={h.edges}
        share={earn.share}
        cushion={vault.tiers.weekday.cushion}
        label={`Earnings-night gaps across ${rc.gaps.tickers.universe} US stocks and funds`}
      />
      <figcaption className="mt-2 text-[14px]">
        Earnings-night gaps, {rc.gaps.period.first_close.slice(0, 4)} to{" "}
        {rc.gaps.period.last_open.slice(0, 4)}, {earn.n.toLocaleString("en-US")} nights. Red: drops
        past the weekday tier&apos;s cushion. Ends include everything beyond{" "}
        {formatPct(h.edges[h.edges.length - 1], 0)}.
      </figcaption>
    </figure>
  );
}

function SettingsVisual({ rc }: { rc: ReportCard }) {
  const s = rc.backtest.strategies;
  const keys = ["always_weekday", "always_weekend", "afterhours"] as const;
  const maxDebt = Math.max(...keys.map((k) => s[k].bad_debt_usdg));
  const maxYield = Math.max(...keys.map((k) => s[k].net_lender_yield_annualised));
  return (
    <figure className="flex flex-col gap-5">
      {keys.map((k) => (
        <div key={k}>
          <p className="text-[18px] font-bold">{STRATEGY_NAMES[k]}</p>
          <div className="mt-1 grid grid-cols-[7rem_1fr] items-center gap-x-3 gap-y-1 text-[14px]">
            <span>Yield {formatPct(s[k].net_lender_yield_annualised, 2)}</span>
            <span
              className="h-3 rounded-full bg-brass"
              style={{ width: `${(s[k].net_lender_yield_annualised / maxYield) * 100}%` }}
            />
            <span>Bad debt {formatUsd(s[k].bad_debt_usdg)}</span>
            <span
              className="h-3 rounded-full bg-risk"
              style={{ width: `${Math.max(1, (s[k].bad_debt_usdg / maxDebt) * 100)}%` }}
            />
          </div>
        </div>
      ))}
      <figcaption className="text-[14px]">
        {formatUsd(rc.backtest.assumptions.vault_usdg)} USDG vault, {rc.backtest.period.first} to{" "}
        {rc.backtest.period.last}. Historical stock prices, simulated vault.
      </figcaption>
    </figure>
  );
}

function BoardVisual({ vault }: { vault: Vault }) {
  const symbols = Array.from(new Set(vault.markets.map((m) => m.symbol)));
  const limit = Math.max(1, vault.max_share_per_stock * vault.tvl_usdg);
  const find = (s: string, t: string) => vault.markets.find((m) => m.symbol === s && m.tier === t);
  return (
    <figure>
      <div className="grid grid-cols-[4rem_1fr_1fr] gap-x-3 gap-y-2 text-[14px]">
        <span />
        <span className="font-semibold">Weekday tier</span>
        <span className="font-semibold">Weekend tier</span>
        {symbols.map((s) => (
          <div key={s} className="contents">
            <span className="font-display text-[18px]">{s}</span>
            {(["weekday", "weekend"] as const).map((t) => {
              const v = find(s, t)?.vault_supply ?? 0;
              return (
                <span
                  key={t}
                  className="relative h-5 overflow-hidden rounded-[4px] border-[1.25px] border-rule bg-bg"
                  role="img"
                  aria-label={`${s} ${t} tier: ${formatUsd(v)} USDG`}
                >
                  <span
                    className="absolute inset-y-0 left-0 bg-brass"
                    style={{
                      width: `${Math.min(1, v / limit) * 100}%`,
                      transition: "width 400ms var(--ease-ui)",
                    }}
                  />
                </span>
              );
            })}
          </div>
        ))}
      </div>
      <figcaption className="mt-3 text-[14px]">
        The vault right now: {formatUsd(vault.tvl_usdg)} USDG
        {vault.simulation.oracle ? " (simulation)" : ""}.
      </figcaption>
    </figure>
  );
}

function TelegramVisual() {
  const q = useQuery({ queryKey: ["reasons", "latest"], queryFn: () => api.reasons(0) });
  const card = q.data?.items[0];
  if (!card)
    return (
      <p className="text-[18px]">
        No telegrams yet. The first one prints at the next plan before the close.
      </p>
    );
  return <Telegram card={card} compact />;
}

function ReplayVisual({ scenario }: { scenario: Scenario }) {
  const r = useReplay(scenario.id);
  if (!r.data) return <p aria-busy="true">Loading the replay.</p>;
  const o = r.data.vaults.always_weekday.bad_debt_usdg;
  const a = r.data.vaults.afterhours.bad_debt_usdg;
  return (
    <figure className="grid grid-cols-2 gap-4">
      {[
        ["Ordinary vault", o],
        ["Afterhours", a],
      ].map(([name, v]) => (
        <div
          key={name as string}
          className="rounded-[12px] border-[1.25px] border-rule bg-surface p-4"
        >
          <p className="font-display text-[24px]">{name}</p>
          <p className="mt-2 text-[14px] font-semibold">Bad debt</p>
          <p className="text-[36px] font-bold leading-none">{formatUsd(v as number)}</p>
          <p className="text-[14px]">USDG</p>
        </div>
      ))}
      <figcaption className="col-span-2 text-[14px]">
        {scenario.ticker}, {scenario.session_prev}, {formatUsd(r.data.vault_usdg)} USDG vault.
        Historical stock prices, simulated vault.
      </figcaption>
    </figure>
  );
}

function ReportVisual({ rc }: { rc: ReportCard }) {
  const shipped = rc.model.acceptance.shipped;
  const perf = rc.model.shipped_performance.overall;
  const ah = rc.backtest.strategies.afterhours;
  const wd = rc.backtest.strategies.always_weekday;
  return (
    <dl className="grid grid-cols-2 gap-6">
      <div>
        <dt className="text-[14px] font-semibold">
          Forecast misses, target {formatPct(rc.model.acceptance.alpha, 0)}
        </dt>
        <dd className="font-display text-[48px] leading-none">{formatPct(perf.miss_rate, 2)}</dd>
        <dd className="text-[14px]">
          {perf.n.toLocaleString("en-US")} held-out closed periods ({shipped})
        </dd>
      </div>
      <div>
        <dt className="text-[14px] font-semibold">Afterhours lender yield</dt>
        <dd className="font-display text-[48px] leading-none">
          {formatPct(ah.net_lender_yield_annualised, 2)}
        </dd>
        <dd className="text-[14px]">
          vs {formatPct(wd.net_lender_yield_annualised, 2)} always weekday
        </dd>
      </div>
      <div>
        <dt className="text-[14px] font-semibold">Bad debt, Afterhours</dt>
        <dd className="font-display text-[48px] leading-none">{formatUsd(ah.bad_debt_usdg)}</dd>
        <dd className="text-[14px]">vs {formatUsd(wd.bad_debt_usdg)} USDG always weekday</dd>
      </div>
      <div>
        <dt className="text-[14px] font-semibold">Backtest</dt>
        <dd className="font-display text-[48px] leading-none">
          {rc.backtest.period.closed_periods.toLocaleString("en-US")}
        </dd>
        <dd className="text-[14px]">closed periods, historical stock prices, simulated vault</dd>
      </div>
    </dl>
  );
}

interface Step {
  id: string;
  title: string;
  body: React.ReactNode;
  visual: React.ReactNode;
}

function useWideMotion(): boolean {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    const wide = window.matchMedia("(min-width: 1024px)");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setOk(wide.matches && !reduce.matches);
    update();
    wide.addEventListener("change", update);
    reduce.addEventListener("change", update);
    return () => {
      wide.removeEventListener("change", update);
      reduce.removeEventListener("change", update);
    };
  }, []);
  return ok;
}

function Story({ steps }: { steps: Step[] }) {
  const pinned = useWideMotion();
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!pinned || !root.current) return;
    let cleanup = () => {};
    let cancelled = false;
    void (async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([
        import("gsap"),
        import("gsap/ScrollTrigger"),
      ]);
      if (cancelled || !root.current) return;
      gsap.registerPlugin(ScrollTrigger);
      const triggers = Array.from(root.current.querySelectorAll<HTMLElement>("[data-step]")).map(
        (el, i) =>
          ScrollTrigger.create({
            trigger: el,
            start: "top 60%",
            end: "bottom 60%",
            onToggle: (self) => self.isActive && setActive(i),
          }),
      );
      cleanup = () => triggers.forEach((t) => t.kill());
    })();
    return () => {
      cancelled = true;
      cleanup();
    };
  }, [pinned]);
  return (
    <div ref={root} className={pinned ? "grid grid-cols-[1fr_1.1fr] gap-16" : ""}>
      <ol className="flex flex-col">
        {steps.map((s, i) => (
          <li
            key={s.id}
            data-step
            className={
              pinned
                ? "flex min-h-[80vh] flex-col justify-center"
                : "border-t-[1.25px] border-rule py-12"
            }
            style={
              pinned
                ? {
                    boxShadow:
                      active === i ? "inset 3px 0 0 var(--c-brass)" : "inset 3px 0 0 transparent",
                    paddingLeft: 24,
                    transition: "box-shadow 300ms var(--ease-ui)",
                  }
                : undefined
            }
          >
            <h3 className="text-[36px] sm:text-[48px]">{s.title}</h3>
            <div className="mt-4 flex flex-col gap-4 text-[18px]">{s.body}</div>
            {!pinned && <div className="mt-8">{s.visual}</div>}
          </li>
        ))}
      </ol>
      {pinned && (
        <div className="relative">
          <div className="sticky top-[15vh] grid min-h-[70vh] items-center">
            {steps.map((s, i) => (
              <div
                key={s.id}
                aria-hidden={active !== i}
                className="col-start-1 row-start-1"
                style={{
                  opacity: active === i ? 1 : 0,
                  visibility: active === i ? "visible" : "hidden",
                  transition: "opacity 300ms var(--ease-ui), visibility 300ms",
                }}
              >
                {s.visual}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function LandingStory() {
  const rcq = useReportCard();
  const vq = useVault();
  const sq = useScenarios();
  if (!rcq.data || !vq.data) {
    return rcq.isError || vq.isError ? (
      <p role="alert">Can&apos;t load the story&apos;s data. {RETRY_TEXT}</p>
    ) : (
      <p aria-busy="true">Loading the numbers.</p>
    );
  }
  const rc = rcq.data;
  const vault = vq.data;
  const h = rc.gaps.histograms.universe.segments;
  const edges = rc.gaps.histograms.universe.edges;
  const cushion = vault.tiers.weekday.cushion;
  const earn = shareBelow(edges, h.earnings.share, cushion);
  const night = shareBelow(edges, h.overnight.share, cushion);
  const s = rc.backtest.strategies;
  const worst = (sq.data?.scenarios ?? []).reduce<Scenario | null>(
    (a, b) => (a === null || b.g < a.g ? b : a),
    null,
  );
  const steps: Step[] = [
    {
      id: "gaps",
      title: "Closed markets gap.",
      body: (
        <>
          <p>
            On an ordinary night, {formatPct(night.share, 2)} of US stocks open{" "}
            {formatPct(night.drop)} or more below the close. On earnings nights it is{" "}
            {formatPct(earn.share, 1)}.
          </p>
          <p>
            A drop that size is past the {formatPct(cushion)} cushion of a{" "}
            {formatPct(vault.tiers.weekday.lltv)} LLTV market: a loan at the limit reopens worth
            less than its debt, and lenders take the loss.
          </p>
        </>
      ),
      visual: <GapVisual rc={rc} vault={vault} />,
    },
    {
      id: "settings",
      title: "Both fixed settings lose.",
      body: (
        <>
          <p>
            Lend at {formatPct(rc.backtest.chosen.weekday_lltv)} LLTV all the time and the gaps cost{" "}
            {formatUsd(s.always_weekday.bad_debt_usdg)} USDG of bad debt in the backtest.
          </p>
          <p>
            Lend at {formatPct(rc.backtest.chosen.weekend_lltv)} all the time and it is safer, but
            lenders earn {formatPct(s.always_weekend.net_lender_yield_annualised, 2)} instead of{" "}
            {formatPct(s.always_weekday.net_lender_yield_annualised, 2)}.
          </p>
        </>
      ),
      visual: <SettingsVisual rc={rc} />,
    },
    {
      id: "board",
      title: "So the vault moves before the bell.",
      body: (
        <p>
          Before each close, Afterhours forecasts the bad-case drop for every stock and moves money
          that is not lent out to the tier whose cushion covers it. When the forecast allows it
          again, the money goes back.
        </p>
      ),
      visual: <BoardVisual vault={vault} />,
    },
    {
      id: "telegram",
      title: "Every move prints a reason.",
      body: (
        <p>
          Each reallocation comes with a reason card: the forecast, what drove it, and the rule that
          fired. Its hash is written onchain, so anyone can check the reason was not changed
          afterwards. <Link href="/ledger">See the ledger</Link>.
        </p>
      ),
      visual: <TelegramVisual />,
    },
    ...(worst
      ? [
          {
            id: "replay",
            title: "Replay the worst night.",
            body: (
              <p>
                {worst.ticker} opened {formatPct(Math.abs(worst.g))} below its close on{" "}
                {worst.session_next}. Here is what an ordinary vault and Afterhours would have lost.{" "}
                <Link href="/replay">Replay this night</Link>.
              </p>
            ),
            visual: <ReplayVisual scenario={worst} />,
          },
        ]
      : []),
    {
      id: "report",
      title: "Checked against history.",
      body: (
        <p>
          {rc.model.first_sentence} <Link href="/report-card">Read the report card</Link>.
        </p>
      ),
      visual: <ReportVisual rc={rc} />,
    },
  ];
  return <Story steps={steps} />;
}
