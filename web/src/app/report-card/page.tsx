import type { Metadata } from "next";

import { ReportCardView } from "@/components/ReportCardView";

export const metadata: Metadata = { title: "Report card | Afterhours" };

export default function ReportCardPage() {
  return <ReportCardView />;
}
