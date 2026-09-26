import { Hero } from "@/components/Hero";
import { SunburstDivider } from "@/art/SunburstDivider";

export default function Home() {
  return (
    <>
      <Hero />
      <SunburstDivider className="mx-auto mt-16 max-w-[1280px] px-4 sm:px-8" />
      <section className="mx-auto max-w-[1280px] px-4 py-16 sm:px-8">
        <h2 className="text-[36px] sm:text-[48px]">The market closes. The token does not.</h2>
        <p className="mt-4 text-[18px]">
          Stock Tokens trade around the clock, but their price feeds follow the exchange: over the
          last eight weekends every Stock Token feed on Robinhood Chain stopped moving from Friday
          20:00 to Sunday 20:00 New York time. Afterhours lends aggressively when the market is open
          and calm, and moves lender money to safer markets before it closes into risk.
        </p>
      </section>
    </>
  );
}
