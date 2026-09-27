import type { Metadata } from "next";
import { Bodoni_Moda, Hanken_Grotesk } from "next/font/google";

import { Grain } from "@/components/Grain";
import { Providers } from "@/components/Providers";
import { SimulationBanner } from "@/components/SimulationBanner";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { StatusSchema } from "@/lib/api";
import { parsePublicConfig } from "@/lib/config";
import { simulationParts } from "@/lib/simulation";
import type { Phase } from "@/lib/phase";

import "./globals.css";

const display = Bodoni_Moda({ variable: "--font-bodoni", subsets: ["latin"], display: "swap" });
const text = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Afterhours",
  description:
    "A lending vault for Stock Tokens that pulls back before the market closes into risk.",
};

/** The banner text from the public config, so the server can render it in the first paint. */
async function initialSimulation(): Promise<string | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) return null;
  try {
    const res = await fetch(new URL("/v1/config/public", base), {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    return simulationParts(parsePublicConfig(await res.json())) || null;
  } catch {
    return null;
  }
}

/** Render the first paint in the right phase, from the API's session state. */
async function initialPhase(): Promise<Phase> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) return "day";
  try {
    const res = await fetch(new URL("/v1/status", base), {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    const status = StatusSchema.parse(await res.json());
    return status.state === "open" ? "day" : "night";
  } catch {
    return "day";
  }
}

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const [phase, simulation] = await Promise.all([initialPhase(), initialSimulation()]);
  return (
    <html lang="en" data-phase={phase} className={`${display.variable} ${text.variable}`}>
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
        >
          Skip to content
        </a>
        <Providers initialPhase={phase}>
          <SimulationBanner initial={simulation} />
          <SiteHeader />
          <main id="main" className="min-h-[80svh]">
            {children}
          </main>
          <SiteFooter />
        </Providers>
        <Grain />
      </body>
    </html>
  );
}
