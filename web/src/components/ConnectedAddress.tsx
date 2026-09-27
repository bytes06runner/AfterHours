"use client";

/** Rendered only inside the wallet providers: hands the connected address to the checker. */
import { useAccount } from "wagmi";

export default function ConnectedAddress({ onUse }: { onUse: (a: string) => void }) {
  const { address, isConnected } = useAccount();
  if (!isConnected || !address) return null;
  return (
    <button
      type="button"
      className="btn btn-quiet !min-h-[40px] !text-[16px]"
      onClick={() => onUse(address)}
    >
      Use my connected wallet
    </button>
  );
}
