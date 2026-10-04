import { Hero } from "@/components/Hero";
import { SunburstDivider } from "@/art/SunburstDivider";
import { ClosedFeeds } from "@/components/ClosedFeeds";
import { FactsBand } from "@/components/FactsBand";
import { LandingStory } from "@/components/LandingStory";
import { RegimesNow } from "@/components/RegimesNow";

export default function Home() {
  return (
    <>
      <Hero />
      <div className="mt-16">
        <FactsBand />
      </div>
      <SunburstDivider className="mx-auto mt-16 max-w-[1440px] px-4 sm:px-8" />
      <section className="mx-auto max-w-[1440px] px-4 py-16 sm:px-8">
        <h2 className="text-[36px] sm:text-[48px]">The market closes. The token does not.</h2>
        <ClosedFeeds />
        <h3 className="mt-10 text-[24px] sm:text-[36px]">Frozen today, thin tomorrow</h3>
        <p className="mt-2 max-w-[72ch] text-[18px]">
          Robinhood plans weekend trading for a curated list of stocks and ETFs, pending regulatory
          review. A weekend price from one venue can be thin and gap. So for every Stock Token,
          Afterhours reads which price regime it is in right now, and how far its price can be
          trusted.
        </p>
        <RegimesNow />
        <div className="mt-12">
          <LandingStory />
        </div>
      </section>
    </>
  );
}
