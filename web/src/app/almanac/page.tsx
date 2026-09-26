import type { Metadata } from "next";

import { AlmanacView } from "@/components/AlmanacView";

export const metadata: Metadata = { title: "Almanac | Afterhours" };

export default function AlmanacPage() {
  return <AlmanacView />;
}
