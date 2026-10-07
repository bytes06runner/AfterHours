import type { Metadata } from "next";

import { CuratorView } from "@/components/CuratorView";

export const metadata: Metadata = { title: "Curator view | Afterhours" };

export default function CuratorsPage() {
  return <CuratorView />;
}
