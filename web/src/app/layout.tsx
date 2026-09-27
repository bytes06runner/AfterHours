import type { Metadata } from "next";
import { Bodoni_Moda, Hanken_Grotesk } from "next/font/google";
import PlausibleProvider from "next-plausible";

import { Grain } from "@/components/Grain";
import { Providers } from "@/components/Providers";
import { SimulationBanner } from "@/components/SimulationBanner";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { StatusSchema } from "@/lib/api";
import { parsePublicConfig, type PublicConfig } from "@/lib/config";
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

/** The public config, read on the server (banner text in the first paint, analytics host). */
async function serverConfig(): Promise<PublicConfig | null> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) return null;
  try {
    const res = await fetch(new URL("/v1/config/public", base), {
      cache: "no-store",
      signal: AbortSignal.timeout(1500),
    });
    return parsePublicConfig(await res.json());
  } catch {
    return null;
  }
}

/** Plausible's site script, only from the host in config (web.analytics.script_host). */
function analyticsSrc(pub: PublicConfig | null): string | null {
  const src = process.env.NEXT_PUBLIC_PLAUSIBLE_SRC;
  const host = pub?.analytics?.script_host;
  if (!src || !host) return null;
  try {
    return new URL(src).origin === new URL(host).origin ? src : null;
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
  const [phase, pub] = await Promise.all([initialPhase(), serverConfig()]);
  const simulation = pub ? simulationParts(pub) || null : null;
  const analytics = analyticsSrc(pub);
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
        {analytics && <PlausibleProvider src={analytics} />}
      </body>
    </html>
  );
}
