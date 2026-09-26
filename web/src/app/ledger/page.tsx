import type { Metadata } from "next";

import { LedgerView } from "@/components/LedgerView";

export const metadata: Metadata = { title: "Ledger | Afterhours" };

export default function LedgerPage() {
  return <LedgerView />;
}
