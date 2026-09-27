import Link from "next/link";

/** Footer: a stepped skyline silhouette, the pages, and what everything on screen is. */
const TOWERS = [
  [0, 40, 1],
  [56, 64, 2],
  [128, 32, 1],
  [168, 88, 3],
  [264, 48, 1],
  [320, 72, 2],
  [400, 36, 1],
  [444, 96, 3],
  [548, 56, 2],
  [612, 40, 1],
  [660, 80, 2],
  [748, 44, 1],
  [800, 104, 3],
  [912, 52, 1],
  [972, 76, 2],
  [1056, 40, 1],
  [1104, 64, 2],
] as const;

function Skyline() {
  return (
    <svg
      viewBox="0 0 1200 110"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="block h-[72px] w-full sm:h-[110px]"
    >
      {TOWERS.map(([x, h, steps]) => {
        const w = 48 + steps * 8;
        const top = 110 - h;
        let d = `M${x} 110 V${top + steps * 12}`;
        for (let s = 1; s <= steps; s++) d += ` H${x + s * 6} V${top + (steps - s) * 12}`;
        d += ` H${x + w - steps * 6}`;
        for (let s = steps - 1; s >= 0; s--) d += ` V${top + (steps - s) * 12} H${x + w - s * 6}`;
        return <path key={x} d={`${d} V110 Z`} fill="var(--c-surface)" />;
      })}
    </svg>
  );
}

const PAGES = [
  { href: "/vault", label: "Vault" },
  { href: "/almanac", label: "Almanac" },
  { href: "/ledger", label: "Ledger" },
  { href: "/replay", label: "Replay" },
  { href: "/report-card", label: "Report card" },
];

export function SiteFooter() {
  return (
    <footer className="mt-24">
      <Skyline />
      <div className="bg-surface">
        <div className="mx-auto grid max-w-[1440px] gap-8 px-4 py-10 sm:px-8 md:grid-cols-[1fr_auto]">
          <div>
            <p className="font-display text-[36px] leading-none">Afterhours</p>
            <p className="mt-3 max-w-[60ch] text-[14px]">
              A lending vault for Robinhood Stock Tokens. The running demo is a simulation on a
              local chain. Backtests are historical stock prices, simulated vault, with modelled
              rates. Nothing here is financial advice.
            </p>
          </div>
          <nav
            aria-label="Footer"
            className="flex flex-wrap gap-x-6 gap-y-2 text-[16px] font-semibold"
          >
            {PAGES.map((p) => (
              <Link key={p.href} href={p.href} className="no-underline hover:underline">
                {p.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>
    </footer>
  );
}
