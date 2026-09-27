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
import { FrontierChart } from "@/charts/FrontierChart";
import { useInView } from "@/charts/useInView";
import { SplitFlap } from "@/components/SplitFlap";
import {
  api,
  type DecisionUniverse,
  type ReportCard,
  type Scenario,
  type Vault,
  RETRY_TEXT,
} from "@/lib/api";
import { useReplay, useReportCard, useScenarios, useVault } from "@/lib/queries";
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

const TIER_LABEL: Record<string, string> = {
  weekday: "Weekday tier",
  middle: "Middle tier",
  weekend: "Weekend tier",
};

function BoardVisual({ vault }: { vault: Vault }) {
  const symbols = Array.from(new Set(vault.markets.map((m) => m.symbol)));
  const limit = Math.max(1, vault.max_share_per_stock * vault.tvl_usdg);
  const tiers = Object.entries(vault.tiers)
    .filter(([, t]) => t)
    .sort((a, b) => b[1].lltv - a[1].lltv)
    .map(([n]) => n);
  const find = (s: string, t: string) => vault.markets.find((m) => m.symbol === s && m.tier === t);
  return (
    <figure>
      <div
        className="grid gap-x-3 gap-y-2 text-[14px]"
        style={{ gridTemplateColumns: `4rem ${tiers.map(() => "1fr").join(" ")}` }}
      >
        <span />
        {tiers.map((t) => (
          <span key={t} className="font-semibold">
            {TIER_LABEL[t]}
          </span>
        ))}
        {symbols.map((s) => (
          <div key={s} className="contents">
            <span className="font-display text-[18px]">{s}</span>
            {tiers.map((t) => {
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

function CompareVisual({ u }: { u: DecisionUniverse }) {
  const [ref, shown] = useInView<HTMLElement>(0.4);
  // Digits start at zero and flip to the measured value when the step scrolls into view.
  const flip = (v: string) => (shown ? v : v.replace(/[0-9]/g, "0"));
  const cells = [
    { label: "Lender yield", b: formatPct(u.b.yield, 2), o: formatPct(u.nearest_blend.yield, 2) },
    {
      label: "Bad debt (USDG)",
      b: formatUsd(u.b.bad_debt),
      o: formatUsd(u.nearest_blend.bad_debt),
    },
    {
      label: "Worst single night",
      b: formatPct(u.b.worst, 3),
      o: formatPct(u.nearest_blend.worst, 3),
    },
  ];
  return (
    <figure ref={ref}>
      <dl className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        {cells.map((c) => (
          <div key={c.label}>
            <dt className="text-[14px] font-semibold">{c.label}</dt>
            <dd className="text-[30px] leading-none">
              <SplitFlap value={flip(c.b)} label={c.b} />
            </dd>
            <dd className="text-[14px]">
              vs {c.o} for the {formatPct(u.nearest_blend.w, 0)} weekday mix
            </dd>
          </div>
        ))}
      </dl>
      <figcaption className="mt-4 text-[14px]">
        {u.stocks} vault stocks, {u.evaluation.first} to {u.evaluation.last}, settings chosen on
        earlier years only. Historical stock prices, simulated vault.
      </figcaption>
    </figure>
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
  const d = rc.decision;
  const u = d.universes.vault;
  const blends = [...u.blends].sort((a, b) => a.w - b.w);
  const [weekend, weekday] = [blends[0], blends[blends.length - 1]];
  const lossRatio = u.b.bad_debt / u.nearest_blend.bad_debt;
  const loss =
    lossRatio > 0.4 && lossRatio < 0.6
      ? "about half the loss"
      : `${formatPct(1 - lossRatio, 0)} less bad debt`;
  const sameYield = Math.abs(u.b.yield - u.nearest_blend.yield) < 0.001;
  const earn = shareBelow(edges, h.earnings.share, cushion);
  const night = shareBelow(edges, h.overnight.share, cushion);
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
      id: "tradeoff",
      title: "Every fixed mix trades yield for loss.",
      body: (
        <>
          <p>
            Lend at {formatPct(vault.tiers.weekday.lltv)} LLTV all the time and lenders earned{" "}
            {formatPct(weekday.yield, 2)} from {u.evaluation.first} to {u.evaluation.last}, but one
            night cost {formatPct(weekday.worst, 3)} of the vault. At{" "}
            {formatPct(vault.tiers.weekend.lltv)} it is safer, and lenders earned{" "}
            {formatPct(weekend.yield, 2)}.
          </p>
          <p>Every split between the two sits on the grey line.</p>
        </>
      ),
      visual: <FrontierChart u={u} cap={d.cap} height={300} />,
    },
    {
      id: "claim",
      title: `${sameYield ? "The same yield" : "Close to the yield"} as the best fixed mix, ${loss}.`,
      body: (
        <>
          <p>
            Afterhours earned {formatPct(u.b.yield, 2)} against{" "}
            {formatPct(u.nearest_blend.yield, 2)} for the fixed mix with the nearest yield (
            {formatPct(u.nearest_blend.w, 0)} weekday), with {formatUsd(u.b.bad_debt)} USDG of bad
            debt against {formatUsd(u.nearest_blend.bad_debt)}.
          </p>
          <p>
            Its settings were chosen on {d.tuning_years} and tested once on {d.evaluation_years}.
          </p>
        </>
      ),
      visual: <CompareVisual u={u} />,
    },
    {
      id: "board",
      title: "The right tier per stock, pulled back before risky nights.",
      body: (
        <p>
          Each January every stock is rated on the previous year only and may lend in the highest
          tier its rating allows: 91.5%, 86% or 77% loan-to-value. Before each close, if a
          stock&apos;s forecast bad case is too large for any tier, the money borrowers are not
          using goes idle until the risk passes.
        </p>
      ),
      visual: <BoardVisual vault={vault} />,
    },
    {
      id: "telegram",
      title: "Every move prints a reason.",
      body: (
        <p>
          Each move comes with a reason card: the stock&apos;s rating, tonight&apos;s forecast, and
          the rule that fired. Its hash is written onchain, so anyone can check the reason was not
          changed afterwards. <Link href="/ledger">See the ledger</Link>.
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
                {worst.session_next}. Here is what a vault always in the weekday tier and Afterhours
                would have lost. <Link href="/replay">Replay this night</Link>.
              </p>
            ),
            visual: <ReplayVisual scenario={worst} />,
          },
        ]
      : []),
    {
      id: "report",
      title: "We set the rule before we looked.",
      body: (
        <>
          <p>{d.rule}</p>
          <p className="font-semibold">{d.result}</p>
          <p>
            {rc.model.first_sentence} <Link href="/report-card">Read the report card</Link>.
          </p>
        </>
      ),
      visual: <FrontierChart u={u} cap={d.cap} height={300} />,
    },
  ];
  return <Story steps={steps} />;
}
