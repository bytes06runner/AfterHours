/** The committed artifacts must parse with the schemas the pages use. */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, test } from "vitest";

import { ReplaySchema, ScenariosSchema } from "./api";

const artifacts = path.resolve(__dirname, "../../../artifacts/backtest");
const read = (p: string) => JSON.parse(readFileSync(p, "utf8")) as unknown;

describe("replay artifacts", () => {
  test("scenarios parse", () => {
    expect(ScenariosSchema.safeParse(read(path.join(artifacts, "scenarios.json"))).success).toBe(
      true,
    );
  });
  for (const f of readdirSync(path.join(artifacts, "replay"))) {
    test(`${f} parses`, () => {
      const r = ReplaySchema.safeParse(read(path.join(artifacts, "replay", f)));
      expect(r.success ? "ok" : JSON.stringify(r.error.issues.slice(0, 3))).toBe("ok");
    });
  }
});
