"use client";

/**
 * Position checker: any address's positions in the Stock Token lending markets on Robinhood Chain
 * mainnet, in plain sentences: how much is borrowed against what, how close the loan is to its
 * limit, the price at which it would be liquidated, and whether tonight's bad case reaches it.
 * Read-only, from /v1/live/positions. Nothing is signed.
 */
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { ApiError, liveErrorText, type LivePositions } from "@/lib/api";
import { useConfig, useLiveExamples, useLivePositions } from "@/lib/queries";
import { coverageText, formatPct } from "@/lib/time";

import { LiveLabel } from "./LiveLabel";
import { useWalletGate } from "./wallet/WalletGate";
import { useWalletReady } from "./wallet/ready";
import { ZonedTime } from "./ZonedTime";

const ConnectedAddress = dynamic(() => import("./ConnectedAddress"), { ssr: false });

const ADDRESS = /^0x[0-9a-fA-F]{40}$/;
const short = (a: string) => `${a.slice(0, 6)}…${a.slice(-4)}`;
const num = (x: number, d = 2) => x.toLocaleString("en-US", { maximumFractionDigits: d });

type Pos = LivePositions["positions"][number];

function PositionCard({ p }: { p: Pos }) {
  // The loan token's own symbol, read onchain; its address if it has none.
  const unit = p.loan_symbol ?? `of token ${short(p.loan_token)}`;
  const value = p.price !== null ? p.collateral_tokens * p.price : null;
  const seg: Record<string, string> = {
    earnings: "earnings night",
    weekend: "weekend",
    holiday: "holiday",
    overnight: "night",
  };
  return (
    <article
      data-testid="position"
      className="rounded-[12px] border-[1.25px] border-rule bg-surface p-5"
      style={
        p.breach_tonight ? { outline: "2px solid var(--c-risk)", outlineOffset: 3 } : undefined
      }
    >
      <h3 className="font-display text-[28px] leading-none">
        {p.symbol}
        <span className="ml-3 font-sans text-[16px] font-semibold">
          market that lends up to {formatPct(p.lltv)} of the collateral
        </span>
      </h3>
      <ul className="mt-4 flex flex-col gap-2 text-[17px]">
        {p.borrowed > 0 && (
          <li>
            You borrowed{" "}
            <strong>
              {num(p.borrowed)} {unit}
            </strong>{" "}
            against{" "}
            <strong>
              {num(p.collateral_tokens, 4)} {p.symbol}
            </strong>{" "}
            tokens
            {value !== null ? `, worth ${num(value)} ${unit} now` : ""}.
          </li>
        )}
        {p.borrowed === 0 && p.collateral_tokens > 0 && (
          <li>
            You have{" "}
            <strong>
              {num(p.collateral_tokens, 4)} {p.symbol}
            </strong>{" "}
            deposited as collateral and nothing borrowed, so there is nothing to liquidate.
          </li>
        )}
        {p.supplied > 0 && (
          <li>
            You lend{" "}
            <strong>
              {num(p.supplied)} {unit}
            </strong>{" "}
            in this market. Lenders lose money only if a borrower&apos;s loan ends up worth more
            than its collateral.
          </li>
        )}
        {p.ltv !== undefined &&
          p.liquidation_price !== undefined &&
          p.drop_to_liquidation !== undefined && (
            <>
              <li>
                Your loan is <strong>{formatPct(p.ltv)}</strong> of your collateral&apos;s value.
                The market liquidates at {formatPct(p.lltv)}.
              </li>
              <li>
                You would be liquidated if {p.symbol} fell to{" "}
                <strong>
                  {num(p.liquidation_price)} {unit}
                </strong>{" "}
                per token, a <strong>{formatPct(p.drop_to_liquidation)}</strong> fall from{" "}
                {p.price !== null ? num(p.price) : "now"}.
              </li>
              {p.tonight ? (
                <li
                  className="font-semibold"
                  style={{ color: p.breach_tonight ? "var(--c-risk)" : "var(--c-safe)" }}
                  data-testid="tonight"
                >
                  {p.breach_tonight
                    ? `Tonight's bad case, a ${formatPct(p.tonight.bad_case_drop)} fall, would reach your liquidation price.`
                    : `Tonight's bad case is a ${formatPct(p.tonight.bad_case_drop)} fall, short of your liquidation price.`}{" "}
                  <span className="font-normal text-ink">
                    ({seg[p.tonight.period.segment] ?? p.tonight.period.segment} until{" "}
                    <ZonedTime iso={p.tonight.period.ends} />; {coverageText(p.tonight)}.)
                  </span>
                </li>
              ) : (
                <li>No forecast for {p.symbol} tonight.</li>
              )}
            </>
          )}
      </ul>
    </article>
  );
}

function readAddressFromUrl(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("address") ?? "";
}

export function PositionCheckerView() {
  const [input, setInput] = useState("");
  const [address, setAddress] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const q = useLivePositions(address);
  const examples = useLiveExamples();
  const { data: pub } = useConfig();
  const ready = useWalletReady();
  const { enable } = useWalletGate();

  useEffect(() => {
    const a = readAddressFromUrl();
    if (a) {
      const t = window.setTimeout(() => {
        setInput(a);
        if (ADDRESS.test(a)) setAddress(a);
      }, 0);
      return () => window.clearTimeout(t);
    }
  }, []);

  const check = (a: string) => {
    const v = a.trim();
    setInput(v);
    if (!ADDRESS.test(v)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setAddress(v);
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("address", v);
      window.history.replaceState(null, "", url);
    } catch {
      /* ignore */
    }
  };

  const d = q.data;
  const err = q.error instanceof ApiError ? q.error : null;
  return (
    <div className="mx-auto max-w-[1100px] px-4 pb-24 sm:px-8">
      <h1 className="mt-8 text-[48px] lg:text-[64px]">Check a position</h1>
      <div className="mt-3">
        <LiveLabel block={d?.block} />
      </div>
      <p className="mt-4 max-w-[68ch] text-[18px]">
        See any wallet&apos;s loans against Stock Tokens on{" "}
        {pub?.live?.network ?? "Robinhood Chain"}: how close each one is to being liquidated, and
        whether tonight&apos;s bad case would get there. We only read public data. Nothing is signed
        and nothing leaves your wallet.
      </p>
      <form
        className="mt-6 flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          check(input);
        }}
      >
        <label className="flex flex-col gap-1 text-[14px] font-semibold">
          Wallet address
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="0x…"
            spellCheck={false}
            autoComplete="off"
            className="min-h-[48px] w-full rounded-[10px] border-[1.25px] border-rule bg-bg px-3 font-mono text-[16px]"
          />
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className="btn btn-brass">
            Check
          </button>
          {ready ? (
            <ConnectedAddress onUse={check} />
          ) : (
            <button
              type="button"
              className="btn btn-quiet !min-h-[40px] !text-[16px]"
              onClick={() => enable(true)}
            >
              Connect a wallet instead
            </button>
          )}
        </div>
        {invalid && (
          <p role="alert" className="text-[16px] font-semibold">
            That is not a wallet address. It should start with 0x and have 40 more letters and
            numbers.
          </p>
        )}
      </form>
      {examples.data && examples.data.addresses.length > 0 && (
        <p className="mt-4 text-[16px]">
          Try a live borrower:{" "}
          {examples.data.addresses.map((a, i) => (
            <span key={a}>
              {i > 0 && ", "}
              <button
                type="button"
                className="underline decoration-brass underline-offset-4"
                onClick={() => check(a)}
              >
                {short(a)}
              </button>
            </span>
          ))}
        </p>
      )}
      <section aria-live="polite" className="mt-8 min-h-[200px]">
        {q.isFetching && !d && (
          <p aria-busy="true">Reading {address ? short(address) : ""} on mainnet.</p>
        )}
        {err && (
          <p role="alert" className="text-[18px]">
            {err.status === 400
              ? "That is not a valid address."
              : liveErrorText(err, "Can't reach Robinhood Chain right now. Try again in a minute.")}
          </p>
        )}
        {d && (
          <>
            <p className="text-[16px]">
              {d.positions.length === 0
                ? `No positions for ${short(d.address)} in the ${d.markets_checked} Stock Token lending markets on ${d.network}.`
                : `${d.positions.length} position${d.positions.length > 1 ? "s" : ""} for ${short(d.address)}, read at `}
              {d.positions.length > 0 && <ZonedTime iso={d.as_of} />}
              {d.positions.length > 0 && "."}{" "}
              {pub?.live?.explorer_url && (
                <a
                  href={`${pub.live.explorer_url}/address/${d.address}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  View on the explorer
                </a>
              )}
            </p>
            <div className="mt-4 flex flex-col gap-5">
              {d.positions.map((p) => (
                <PositionCard key={p.market_id} p={p} />
              ))}
            </div>
            <p className="mt-6 text-[14px]">
              Amounts are as of each market&apos;s last update and leave out interest since then.
              Loans through a vault or another app are not shown. Not financial advice.
            </p>
          </>
        )}
      </section>
    </div>
  );
}
