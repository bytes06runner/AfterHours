import type { Metadata } from "next";
import { Bodoni_Moda, Hanken_Grotesk } from "next/font/google";

import { Grain } from "@/components/Grain";
import { Providers } from "@/components/Providers";
import { SimulationBanner } from "@/components/SimulationBanner";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { StatusSchema } from "@/lib/api";
import { Analytics } from "@/components/Analytics";
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

/** The public config, read on the server (banner text in the first paint, analytics). */
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

/**
 * GoatCounter, in production only: the script from `web.analytics.script_src` and the site's
 * count endpoint from its env var, which must be https on `web.analytics.endpoint_domain`.
 */
function analyticsConfig(pub: PublicConfig | null): { src: string; endpoint: string } | null {
  const endpoint = process.env.NEXT_PUBLIC_GOATCOUNTER_URL;
  const a = pub?.analytics;
  if (process.env.NODE_ENV !== "production" || !endpoint || !a) return null;
  try {
    const host = new URL(endpoint);
    const ok =
      host.protocol === "https:" &&
      (host.hostname === a.endpoint_domain || host.hostname.endsWith(`.${a.endpoint_domain}`));
    return ok ? { src: a.script_src, endpoint } : null;
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
  const analytics = analyticsConfig(pub);
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
        {analytics && <Analytics src={analytics.src} endpoint={analytics.endpoint} />}
      </body>
    </html>
  );
}
