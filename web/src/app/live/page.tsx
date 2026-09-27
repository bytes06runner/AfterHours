import type { Metadata } from "next";

import { RiskBoardView } from "@/components/RiskBoardView";

export const metadata: Metadata = { title: "Live risk board | Afterhours" };

export default function LivePage() {
  return <RiskBoardView />;
}
