"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect } from "react";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useVault } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

import { AllocationBoard } from "./AllocationBoard";
import { BellCountdown } from "./BellCountdown";
import { SessionBadge } from "./SessionBadge";
import { Telegram } from "./Telegram";
import { useWalletGate } from "./wallet/WalletGate";
import { useWalletReady } from "./wallet/ready";

const DepositPanel = dynamic(() => import("./DepositPanel"), {
  ssr: false,
  loading: () => <p aria-busy="true">Loading the wallet.</p>,
});

export function VaultView() {
  const { enable } = useWalletGate();
  const ready = useWalletReady();
  const vault = useVault();
  const latest = useQuery({ queryKey: ["reasons", "latest"], queryFn: () => api.reasons(0) });
  useEffect(() => enable(false), [enable]);
  const v = vault.data;
  return (
    <div className="mx-auto max-w-[1280px] px-4 pb-24 sm:px-8">
      <header className="mt-8 flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="text-[48px] lg:text-[64px]">The vault</h1>
          <p className="mt-3 text-[18px]">
            {v
              ? `${formatUsd(v.tvl_usdg)} USDG in the vault, ${formatUsd(v.placed_usdg)} placed in markets, APY ${formatPct(v.apy, 2)} at current rates.`
              : "Reading the vault onchain."}
          </p>
        </div>
      </header>
      <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(300px,380px)_1fr]">
        <aside className="flex flex-col gap-8">
          <section
            aria-labelledby="position-title"
            className="rounded-[12px] border-[1.25px] border-rule bg-surface p-5"
          >
            <h2 id="position-title" className="text-[24px]">
              Your position
            </h2>
            <div className="mt-4">
              {ready ? <DepositPanel vault={v} /> : <p aria-busy="true">Loading the wallet.</p>}
            </div>
          </section>
          <section aria-label="Session" className="flex flex-col gap-4">
            <SessionBadge />
            <BellCountdown />
          </section>
        </aside>
        <div className="min-w-0">
          <AllocationBoard />
        </div>
      </div>
      <section aria-labelledby="telegrams-title" className="mt-16">
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <h2 id="telegrams-title" className="text-[36px]">
            Latest telegrams
          </h2>
          <Link href="/ledger" className="text-[18px] font-semibold">
            See the ledger
          </Link>
        </div>
        <ul className="mt-6 grid gap-8 xl:grid-cols-3">
          {(latest.data?.items ?? []).slice(0, 3).map((c) => (
            <li key={c.id}>
              <Telegram card={c} compact />
            </li>
          ))}
        </ul>
        {latest.data && latest.data.items.length === 0 && (
          <p className="mt-4 text-[18px]">No moves yet.</p>
        )}
      </section>
    </div>
  );
}
