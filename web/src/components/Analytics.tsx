"use client";

/**
 * GoatCounter page counts (goatcounter.com/help/spa). Automatic counting is turned off
 * (`no_onload`) before the script loads; the first page is counted when it loads and every later
 * route change here. Renders nothing.
 */
import { usePathname } from "next/navigation";
import { useEffect } from "react";

type GoatCounter = { no_onload?: boolean; count?: (v: { path: string }) => void };
declare global {
  interface Window {
    goatcounter?: GoatCounter;
  }
}

const SCRIPT_ID = "goatcounter";
const count = () => window.goatcounter?.count?.({ path: location.pathname + location.search });

export function Analytics({ src, endpoint }: { src: string; endpoint: string }) {
  const pathname = usePathname();

  useEffect(() => {
    if (document.getElementById(SCRIPT_ID)) return;
    window.goatcounter = { no_onload: true };
    const el = document.createElement("script");
    el.id = SCRIPT_ID;
    el.async = true;
    el.src = src;
    el.dataset.goatcounter = endpoint;
    el.onload = count;
    document.body.appendChild(el);
  }, [src, endpoint]);

  // Later navigations; before the script has loaded this does nothing.
  useEffect(() => {
    count();
  }, [pathname]);

  return null;
}
