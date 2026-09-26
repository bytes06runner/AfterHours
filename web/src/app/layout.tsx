import type { Metadata } from "next";
import { Bodoni_Moda, Hanken_Grotesk } from "next/font/google";

import { Grain } from "@/components/Grain";
import { Providers } from "@/components/Providers";
import { SimulationBanner } from "@/components/SimulationBanner";
import { SiteHeader } from "@/components/SiteHeader";
import { StatusSchema } from "@/lib/api";
import type { Phase } from "@/lib/phase";

import "./globals.css";

const display = Bodoni_Moda({ variable: "--font-bodoni", subsets: ["latin"], display: "swap" });
const text = Hanken_Grotesk({ variable: "--font-hanken", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Afterhours",
  description:
    "A lending vault for Stock Tokens that pulls back before the market closes into risk.",
};

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
  const phase = await initialPhase();
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
          <SimulationBanner />
          <SiteHeader />
          <main id="main">{children}</main>
        </Providers>
        <Grain />
      </body>
    </html>
  );
}
