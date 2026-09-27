"use client";

/** Marks data read live from mainnet (the vault elsewhere on the site is a simulation). */
import { useConfig } from "@/lib/queries";

export function LiveLabel({ block }: { block?: number }) {
  const { data } = useConfig();
  const network = data?.live?.network;
  return (
    <p className="badge !border-safe">
      <span aria-hidden="true" className="live-dot" />
      {/* One span: the badge's flex gap would otherwise put a space before the comma. */}
      <span>
        Live{network ? `: ${network} mainnet` : ""}, read-only
        {block !== undefined && (
          <span className="font-normal">, block {block.toLocaleString("en-US")}</span>
        )}
      </span>
    </p>
  );
}
