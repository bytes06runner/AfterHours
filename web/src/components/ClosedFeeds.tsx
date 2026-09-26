"use client";

/** The landing's opening claim, written from the M1 oracle study (via /v1/report-card). */
import { useReportCard } from "@/lib/queries";

function range(first: string | null, last: string | null): string {
  if (!first || !last) return "";
  const f = (iso: string, year: boolean) =>
    new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      ...(year ? { year: "numeric" } : {}),
      timeZone: "America/New_York",
    });
  return ` from ${f(first, false)} to ${f(last, true)}`;
}

export function ClosedFeeds() {
  const { data } = useReportCard();
  const o = data?.oracle;
  const others = o ? o.feeds - o.feeds_without_update : 0;
  return (
    <p className="mt-4 min-h-[5.5em] text-[18px]">
      Stock Tokens trade around the clock, but their price feeds follow the exchange.
      {o && (
        <>
          {" "}
          Over {o.weekends} weekends{range(o.first_weekend_close, o.last_weekend_close)},{" "}
          {o.feeds_without_update} of the {o.feeds} Stock Token price feeds on Robinhood Chain
          posted no update between Friday 20:00 and Sunday 20:00 New York time
          {others > 0 && o.max_seconds_after_window_opened !== null
            ? `; the other ${others} (${o.feeds_with_update.join(", ")}) posted ${o.updates_in_window} updates in all, each within ${Math.ceil(o.max_seconds_after_window_opened / 60)} minutes of Friday 20:00`
            : ""}
          .
        </>
      )}{" "}
      Afterhours lends at full speed when the market is open and calm, and moves lender money to
      safer markets before it closes into risk.
    </p>
  );
}
