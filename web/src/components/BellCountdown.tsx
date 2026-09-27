"use client";

import { usePhase } from "@/lib/phase";
import { countdownParts } from "@/lib/time";

import { useSecondsTo } from "./SessionBadge";
import { SplitFlap } from "./SplitFlap";
import { ZonedTime } from "./ZonedTime";

/** Split-flap countdown to the next closing or opening bell. */
export function BellCountdown() {
  const { live, status } = usePhase();
  const open = live === "day";
  const left = useSecondsTo(open ? status?.next_close : status?.next_open);
  const { h, m, s } = countdownParts(left);
  const label = open ? "Next closing bell" : "Next opening bell";
  return (
    <div>
      <p className="mb-2 text-[18px] font-semibold">{label}</p>
      <div className="text-[36px] sm:text-[48px]">
        <SplitFlap
          value={`${h}:${m}:${s}`}
          label={`${label} in ${h} hours ${m} minutes ${s} seconds`}
        />
      </div>
      {(open ? status?.next_close : status?.next_open) && (
        <p className="mt-2 text-[14px]">
          <ZonedTime iso={(open ? status?.next_close : status?.next_open) as string} />
        </p>
      )}
      {status?.clock === "chain" && (
        <p className="mt-2 text-[14px]">On the chain&apos;s clock ({status.profile} profile).</p>
      )}
    </div>
  );
}
