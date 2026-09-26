"use client";

import dynamic from "next/dynamic";

import { useWalletGate } from "./wallet/WalletGate";
import { useWalletReady } from "./wallet/ready";

const ConnectLazy = dynamic(() => import("./wallet/ConnectLazy"), { ssr: false });

/** Connect button. The wallet libraries load after the first press (or on the vault page). */
export function WalletButton() {
  const { enabled, enable } = useWalletGate();
  // RainbowKit's button needs the wagmi providers, which need the API's public config.
  const ready = useWalletReady();
  if (enabled && ready) return <ConnectLazy />;
  return (
    <button
      type="button"
      className="btn btn-quiet !min-h-[40px] !text-[16px]"
      onClick={() => enable(true)}
      disabled={enabled}
      aria-busy={enabled}
    >
      Connect
    </button>
  );
}
