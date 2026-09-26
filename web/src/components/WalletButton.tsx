"use client";

import dynamic from "next/dynamic";

import { useWalletGate } from "./wallet/WalletGate";

const ConnectLazy = dynamic(() => import("./wallet/ConnectLazy"), { ssr: false });

/** Connect button. The wallet libraries load after the first press (or on the vault page). */
export function WalletButton() {
  const { enabled, enable } = useWalletGate();
  if (enabled) return <ConnectLazy />;
  return (
    <button
      type="button"
      className="btn btn-quiet !min-h-[40px] !text-[16px]"
      onClick={() => enable(true)}
    >
      Connect
    </button>
  );
}
