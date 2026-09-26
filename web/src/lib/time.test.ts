import { describe, expect, it } from "vitest";

import { countdownParts, newYorkClock } from "./time";

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
