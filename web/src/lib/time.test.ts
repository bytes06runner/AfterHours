import { describe, expect, it } from "vitest";

import { countdownParts, coverageText, newYorkClock } from "./time";

describe("time", () => {
  it("reads New York time across daylight saving", () => {
    expect(newYorkClock("2026-09-25T20:00:00Z")).toEqual({ h: 16, m: 0, s: 0 }); // EDT
    expect(newYorkClock("2026-12-04T21:00:00Z")).toEqual({ h: 16, m: 0, s: 0 }); // EST
  });

  it("splits a countdown", () => {
    expect(countdownParts(3 * 3600 + 7 * 60 + 5)).toEqual({ h: "03", m: "07", s: "05" });
    expect(countdownParts(-4)).toEqual({ h: "00", m: "00", s: "00" });
    expect(countdownParts(500 * 3600).h).toBe("99");
  });
});

describe("coverageText", () => {
  it("states the target and the measured held-out share, not 1 in 100 alone", () => {
    const t = {
      alpha: 0.01,
      period: { segment: "weekend" },
      held_out_miss_rate: 0.017257,
      held_out_years: [2017, 2026],
    };
    expect(coverageText(t)).toBe(
      "the forecast aims for a fall beyond it on 1% of closed periods; on held-out years 2017 to 2026 it was beaten on 1.73% of weekend periods, about 1 in 58",
    );
    expect(coverageText({ alpha: 0.01, period: { segment: "overnight" } })).toBe(
      "the forecast aims for a fall beyond it on 1% of closed periods",
    );
  });
});
