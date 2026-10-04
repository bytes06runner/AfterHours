import Link from "next/link";

import { DayNightSwitch } from "./DayNightSwitch";
import { SessionBadge } from "./SessionBadge";
import { WalletButton } from "./WalletButton";

const NAV = [
  { href: "/vault", label: "Vault" },
  { href: "/almanac", label: "Almanac" },
  { href: "/ledger", label: "Ledger" },
  { href: "/replay", label: "Replay" },
  { href: "/report-card", label: "Report card" },
  { href: "/live", label: "Risk board" },
  { href: "/positions", label: "Check a position" },
  { href: "/agents", label: "Agents" },
];

export function SiteHeader() {
  return (
    <header className="mx-auto flex max-w-[1440px] items-center gap-4 px-4 py-4 sm:px-8">
      <Link href="/" className="font-display text-[24px] no-underline sm:text-[28px]">
        Afterhours
      </Link>
      <nav aria-label="Main" className="ml-4 hidden gap-6 text-[16px] font-semibold xl:flex">
        {NAV.map((n) => (
          <Link key={n.href} href={n.href} className="no-underline hover:underline">
            {n.label}
          </Link>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-3">
        <span className="hidden md:inline-flex">
          <SessionBadge />
        </span>
        <span className="hidden sm:inline-flex">
          <DayNightSwitch />
        </span>
        <WalletButton />
        <details className="relative xl:hidden">
          <summary className="btn btn-quiet !min-h-[40px] !text-[16px] list-none" aria-label="Menu">
            Menu
          </summary>
          <nav
            aria-label="Main"
            className="absolute right-0 z-50 mt-2 flex w-56 flex-col gap-1 rounded-[12px] border border-rule bg-bg p-2"
          >
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="rounded-[10px] px-3 py-2 font-semibold no-underline hover:bg-surface"
              >
                {n.label}
              </Link>
            ))}
            <span className="flex items-center justify-between px-3 py-2 font-semibold sm:hidden">
              Day and night
              <DayNightSwitch />
            </span>
          </nav>
        </details>
      </div>
    </header>
  );
}
