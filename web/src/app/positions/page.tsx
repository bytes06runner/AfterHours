import type { Metadata } from "next";

import { PositionCheckerView } from "@/components/PositionCheckerView";

export const metadata: Metadata = { title: "Check a position | Afterhours" };

export default function PositionsPage() {
  return <PositionCheckerView />;
}
