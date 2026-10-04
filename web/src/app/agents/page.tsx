import type { Metadata } from "next";

import { AgentsView } from "@/components/AgentsView";

export const metadata: Metadata = { title: "Agents | Afterhours" };

export default function AgentsPage() {
  return <AgentsView />;
}
