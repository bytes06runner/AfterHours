/**
 * Screenshot QA (docs/DESIGN.md section 11): each page at 1440, 1024 and 390 px wide.
 *   WEB_BASE_URL=... tsx scripts/screens.ts <label> <out-dir> [path ...]
 * <label> names the state being captured ("day", "night"); with "bell" the script presses
 * "Preview the close" and captures mid-sequence.
 */
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

const WIDTHS = [
  { w: 1440, h: 900 },
  { w: 1024, h: 768 },
  { w: 390, h: 844 },
];

async function main(): Promise<void> {
  const [label, outDir, ...paths] = process.argv.slice(2);
  const base = process.env.WEB_BASE_URL;
  if (!label || !outDir || !base)
    throw new Error("usage: WEB_BASE_URL=... screens.ts <label> <out> [paths]");
  const pages = paths.length ? paths : ["/"];
  const browser = await chromium.launch();
  try {
    for (const path of pages) {
      const name = path === "/" ? "landing" : path.replace(/^\//, "").replace(/\//g, "-");
      const dir = join(outDir, name);
      mkdirSync(dir, { recursive: true });
      for (const { w, h } of WIDTHS) {
        const ctx = await browser.newContext({
          viewport: { width: w, height: h },
          deviceScaleFactor: 1,
        });
        const page = await ctx.newPage();
        await page.goto(new URL(path, base).toString(), { waitUntil: "networkidle" });
        await page.waitForTimeout(1500);
        if (label === "bell") {
          const wasNight = await page.evaluate(
            () => document.documentElement.dataset.phase === "night",
          );
          await page.getByRole("button", { name: "Preview the close" }).click();
          await page.evaluate(() => window.scrollTo(0, 0));
          // Mid-sequence: about 1.2 s into the 2.4 s closing bell.
          await page.waitForTimeout(wasNight ? 1600 : 1200);
          await page.screenshot({ path: join(dir, `bell-${w}.png`) });
        } else {
          await page.screenshot({ path: join(dir, `${label}-${w}.png`), fullPage: true });
        }
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > window.innerWidth,
        );
        console.log(`${name} ${label} ${w}px${overflow ? " HORIZONTAL OVERFLOW" : ""}`);
        await ctx.close();
      }
    }
  } finally {
    await browser.close();
  }
}

main().catch((error: unknown) => {
  console.error(error);
  process.exit(1);
});
