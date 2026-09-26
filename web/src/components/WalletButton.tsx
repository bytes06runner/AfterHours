"use client";

/**
 * Connect button. RainbowKit and wagmi are large, so they load only after the first press.
 */
import dynamic from "next/dynamic";
import { useState } from "react";

const WalletRoot = dynamic(() => import("./WalletRoot"), {
  ssr: false,
  loading: () => (
    <button type="button" className="btn btn-quiet !min-h-[40px] !text-[16px]" disabled>
      Connecting
    </button>
  ),
});

export function WalletButton() {
  const [wanted, setWanted] = useState(false);
  if (wanted) return <WalletRoot openOnMount />;
  return (
    <button
      type="button"
      className="btn btn-quiet !min-h-[40px] !text-[16px]"
      onClick={() => setWanted(true)}
    >
      Connect
    </button>
  );
}
