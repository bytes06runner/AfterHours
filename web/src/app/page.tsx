import { Hero } from "@/components/Hero";
import { SunburstDivider } from "@/art/SunburstDivider";
import { ClosedFeeds } from "@/components/ClosedFeeds";
import { FactsBand } from "@/components/FactsBand";
import { LandingStory } from "@/components/LandingStory";

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
        <div className="mt-12">
          <LandingStory />
        </div>
      </section>
    </>
  );
}
