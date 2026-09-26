"use client";

import { useState } from "react";

import type { Card } from "@/lib/api";
import { useConfig } from "@/lib/queries";
import { verifyOnChain, type Verdict } from "@/lib/verify";

function short(hex: string): string {
  return `${hex.slice(0, 10)}…${hex.slice(-6)}`;
}

/** Recomputes the card hash in this browser and checks the registry event onchain. */
export function VerifyBadge({ card }: { card: Card }) {
  const { data: pub } = useConfig();
  const [state, setState] = useState<"idle" | "checking" | Verdict>("idle");
  const registry = (pub?.deployment as { registry?: { address?: string } } | undefined)?.registry
    ?.address;
  const rpc = pub?.chain.rpc_url;
  const explorer = pub?.chain.explorer_url;

  async function run() {
    if (!rpc || !registry) return;
    setState("checking");
    setState(await verifyOnChain(card, rpc, registry));
  }

  if (state === "idle" || state === "checking") {
    return (
      <button
        type="button"
        className="btn btn-quiet !min-h-[40px] !text-[16px]"
        onClick={run}
        disabled={!rpc || !registry || state === "checking"}
      >
        {state === "checking" ? "Checking onchain" : "Verify on chain"}
      </button>
    );
  }
  const ok = state.status === "matched";
  const txLink =
    "tx" in state && state.tx ? (
      explorer ? (
        <a href={`${explorer}/tx/${state.tx}`} target="_blank" rel="noreferrer">
          {short(state.tx)}
        </a>
      ) : (
        <span>{short(state.tx)}</span>
      )
    ) : null;
  return (
    <div
      role="status"
      className="rounded-[12px] border-[1.25px] px-3 py-2 text-[14px]"
      style={{ borderColor: ok ? "var(--c-safe)" : "var(--c-risk)" }}
    >
      <p className="font-bold" style={{ color: ok ? "var(--c-safe)" : "var(--c-risk)" }}>
        {ok && "Matched onchain"}
        {state.status === "mismatched" && "Mismatch: the onchain hash differs from this card"}
        {state.status === "event_missing" && "No registry event in that transaction"}
        {state.status === "no_tx" && "Not anchored yet"}
        {state.status === "unreachable" && "Can't reach the chain. Try again in a moment."}
      </p>
      <p className="mt-1">
        Hash computed in your browser: <code className="font-sans">{short(state.recomputed)}</code>
      </p>
      {"onchain" in state && (
        <p>
          Registry event #{String(state.seq)} in block {String(state.block)}:{" "}
          <code className="font-sans">{short(state.onchain)}</code>
        </p>
      )}
      {txLink && <p>Transaction {txLink}</p>}
    </div>
  );
}
