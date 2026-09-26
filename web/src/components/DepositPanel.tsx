"use client";

/**
 * Deposit USDG and withdraw (docs/DESIGN.md DepositPanel). Only mounted inside the wallet
 * providers. Previews come from the vault itself (previewDeposit) and from the API's
 * "withdrawable now" (idle cash plus the liquidity market), because Vault V2's maxWithdraw
 * always returns 0.
 */
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { formatUnits, parseAbi, parseUnits, type Address } from "viem";
import {
  useAccount,
  useChainId,
  usePublicClient,
  useReadContracts,
  useSwitchChain,
  useWriteContract,
} from "wagmi";
import { waitForTransactionReceipt } from "wagmi/actions";
import { useConfig as useWagmiConfig } from "wagmi";

import { apiBase, type Vault } from "@/lib/api";
import { keys, useConfig } from "@/lib/queries";
import { formatPct, formatUsd } from "@/lib/time";

const ERC20 = parseAbi([
  "function balanceOf(address) view returns (uint256)",
  "function allowance(address,address) view returns (uint256)",
  "function approve(address,uint256) returns (bool)",
  "function decimals() view returns (uint8)",
]);
const VAULT = parseAbi([
  "function deposit(uint256 assets, address onBehalf) returns (uint256)",
  "function withdraw(uint256 assets, address receiver, address onBehalf) returns (uint256)",
  "function previewDeposit(uint256 assets) view returns (uint256)",
  "function balanceOf(address) view returns (uint256)",
  "function convertToAssets(uint256 shares) view returns (uint256)",
  "function decimals() view returns (uint8)",
]);

type Mode = "deposit" | "withdraw";

export default function DepositPanel({ vault }: { vault: Vault | undefined }) {
  const { data: pub } = useConfig();
  const { address, isConnected } = useAccount();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();
  const wagmiConfig = useWagmiConfig();
  const client = useQueryClient();
  const { writeContractAsync } = useWriteContract();
  const publicClient = usePublicClient();
  const [mode, setMode] = useState<Mode>("deposit");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const dep = pub?.deployment as
    { vault?: { address: Address }; loan_token?: { address: Address } } | undefined;
  const vaultAddr = dep?.vault?.address;
  const usdg = dep?.loan_token?.address;
  const reads = useReadContracts({
    allowFailure: false,
    query: { enabled: Boolean(address && vaultAddr && usdg), refetchInterval: 10_000 },
    contracts:
      address && vaultAddr && usdg
        ? [
            { address: usdg, abi: ERC20, functionName: "decimals" },
            { address: usdg, abi: ERC20, functionName: "balanceOf", args: [address] },
            { address: usdg, abi: ERC20, functionName: "allowance", args: [address, vaultAddr] },
            { address: vaultAddr, abi: VAULT, functionName: "balanceOf", args: [address] },
            { address: vaultAddr, abi: VAULT, functionName: "decimals" },
          ]
        : [],
  });
  const [dec, walletBal, allowance, shares, shareDec] = (reads.data ?? [6, 0n, 0n, 0n, 18]) as [
    number,
    bigint,
    bigint,
    bigint,
    number,
  ];
  const value = useReadContracts({
    allowFailure: false,
    query: { enabled: Boolean(vaultAddr && shares > 0n) },
    contracts: vaultAddr
      ? [{ address: vaultAddr, abi: VAULT, functionName: "convertToAssets", args: [shares] }]
      : [],
  });
  const positionValue = (value.data?.[0] as bigint | undefined) ?? 0n;
  const parsed = (() => {
    try {
      return amount ? parseUnits(amount, dec) : 0n;
    } catch {
      return 0n;
    }
  })();
  const preview = useReadContracts({
    allowFailure: false,
    query: { enabled: Boolean(vaultAddr && parsed > 0n && mode === "deposit") },
    contracts: vaultAddr
      ? [{ address: vaultAddr, abi: VAULT, functionName: "previewDeposit", args: [parsed] }]
      : [],
  });
  const withdrawable = vault?.withdrawable_now_usdg ?? 0;
  const human = (x: bigint) => Number(formatUnits(x, dec));

  if (!pub?.chain.chain_id) return null;
  if (!isConnected || !address) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-[18px]">Connect a wallet to deposit USDG.</p>
        <ConnectButton label="Connect" chainStatus="none" showBalance={false} />
        {pub.profile === "local" && (
          <p className="text-[14px]">
            Local simulation: add the local chain to your wallet (chain id {pub.chain.chain_id}),
            then use the test USDG faucet here.
          </p>
        )}
      </div>
    );
  }
  if (chainId !== pub.chain.chain_id) {
    return (
      <button
        type="button"
        className="btn btn-brass"
        onClick={() => switchChain({ chainId: pub.chain.chain_id! })}
      >
        Switch to the {pub.profile === "local" ? "local chain" : pub.chain.key}
      </button>
    );
  }

  async function run(label: string, fn: () => Promise<`0x${string}`>) {
    setBusy(label);
    setNotice(null);
    try {
      const hash = await fn();
      await waitForTransactionReceipt(wagmiConfig, { hash });
      return true;
    } catch (error) {
      const e = error as { shortMessage?: string; details?: string; message?: string };
      const detail = e.details && e.details !== e.shortMessage ? ` ${e.details}` : "";
      setNotice(
        `${e.shortMessage ?? e.message?.split("\n")[0] ?? "The transaction failed."}${detail}`,
      );
      return false;
    } finally {
      setBusy(null);
    }
  }

  /** Estimate gas ourselves and add 30%: Vault V2 exits accrue interest and read adapters. */
  async function send(req: Parameters<typeof writeContractAsync>[0]): Promise<`0x${string}`> {
    const gas = publicClient
      ? await publicClient.estimateContractGas({ ...(req as object), account: address } as never)
      : undefined;
    return writeContractAsync({ ...req, gas: gas ? (gas * 13n) / 10n : undefined } as typeof req);
  }

  async function submit() {
    if (!vaultAddr || !usdg || !address || parsed <= 0n) return;
    if (mode === "deposit") {
      if (allowance < parsed) {
        const ok = await run("Approving USDG", () =>
          send({ address: usdg, abi: ERC20, functionName: "approve", args: [vaultAddr, parsed] }),
        );
        if (!ok) return;
      }
      const ok = await run("Depositing USDG", () =>
        send({ address: vaultAddr, abi: VAULT, functionName: "deposit", args: [parsed, address] }),
      );
      if (ok) setNotice(`Deposited ${formatUsd(human(parsed), 2)} USDG.`);
    } else {
      const ok = await run("Withdrawing", () =>
        send({
          address: vaultAddr,
          abi: VAULT,
          functionName: "withdraw",
          args: [parsed, address, address],
        }),
      );
      if (ok) setNotice(`Withdrawn ${formatUsd(human(parsed), 2)} USDG.`);
    }
    setAmount("");
    await reads.refetch();
    await client.invalidateQueries({ queryKey: keys.vault });
  }

  async function faucet() {
    setBusy("Getting test USDG");
    setNotice(null);
    try {
      const res = await fetch(new URL("/v1/sim/faucet", apiBase()), {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ address }),
      });
      const body = (await res.json()) as { detail?: string; usdg?: number };
      setNotice(
        res.ok
          ? `Received ${formatUsd(body.usdg ?? 0)} USDG (sim) and gas.`
          : (body.detail ?? "Faucet failed."),
      );
      await reads.refetch();
    } finally {
      setBusy(null);
    }
  }

  const tooMuch = mode === "withdraw" ? human(parsed) > withdrawable : parsed > walletBal;
  const needsApproval = mode === "deposit" && parsed > 0n && allowance < parsed;
  return (
    <div className="flex flex-col gap-5">
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dt className="text-[14px] font-semibold">Your position</dt>
          <dd className="font-display text-[36px] leading-none">
            {formatUsd(human(positionValue), 2)}
          </dd>
          <dd className="text-[14px]">
            USDG, {formatUsd(Number(formatUnits(shares, shareDec)), 2)} {pub.vault.symbol}
          </dd>
        </div>
        <div>
          <dt className="text-[14px] font-semibold">Vault APY now</dt>
          <dd className="font-display text-[36px] leading-none">{formatPct(vault?.apy ?? 0, 2)}</dd>
          <dd className="text-[14px]">Live supply rates, after idle cash</dd>
        </div>
      </dl>
      <div role="tablist" aria-label="Deposit or withdraw" className="flex gap-2">
        {(["deposit", "withdraw"] as const).map((m) => (
          <button
            key={m}
            role="tab"
            aria-selected={mode === m}
            type="button"
            onClick={() => setMode(m)}
            className={`btn !min-h-[40px] !text-[16px] ${mode === m ? "btn-brass" : "btn-quiet"}`}
          >
            {m === "deposit" ? "Deposit USDG" : "Withdraw"}
          </button>
        ))}
      </div>
      <label className="flex flex-col gap-1 text-[14px] font-semibold">
        Amount in USDG
        <span className="flex gap-2">
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ""))}
            className="min-h-[48px] w-full rounded-[10px] border-[1.25px] border-rule bg-bg px-3 text-[21px] font-bold"
            placeholder="0.00"
          />
          <button
            type="button"
            className="btn btn-quiet !text-[16px]"
            onClick={() =>
              setAmount(
                mode === "deposit"
                  ? formatUnits(walletBal, dec)
                  : String(Math.min(withdrawable, human(positionValue))),
              )
            }
          >
            Max
          </button>
        </span>
      </label>
      <p className="text-[14px]">
        {mode === "deposit"
          ? `Wallet: ${formatUsd(human(walletBal), 2)} USDG.${parsed > 0n && preview.data ? ` You receive about ${formatUsd(Number(formatUnits(preview.data[0] as bigint, shareDec)), 2)} ${pub.vault.symbol}.` : ""} New deposits go to ${vault?.liquidity_market ? vault.liquidity_market.replace(":", "'s ") + " tier market" : "idle cash"} first.`
          : `Available to withdraw now: ${formatUsd(withdrawable, 2)} USDG (idle cash and the liquidity market). Money lent to borrowers comes back as loans are repaid.`}
      </p>
      <button
        type="button"
        className="btn btn-brass"
        disabled={busy !== null || parsed <= 0n || tooMuch}
        onClick={() => void submit()}
      >
        {busy ??
          (mode === "deposit"
            ? needsApproval
              ? "Approve and deposit USDG"
              : "Deposit USDG"
            : "Withdraw")}
      </button>
      {tooMuch && (
        <p className="text-[14px]" role="alert">
          That is more than{" "}
          {mode === "deposit" ? "your wallet holds" : "can be withdrawn right now"}.
        </p>
      )}
      {pub.profile === "local" && (
        <button
          type="button"
          className="btn btn-quiet !text-[16px]"
          disabled={busy !== null}
          onClick={() => void faucet()}
        >
          Get test USDG (sim)
        </button>
      )}
      <p aria-live="polite" className="min-h-[1.5em] text-[16px] font-semibold">
        {notice}
      </p>
    </div>
  );
}
