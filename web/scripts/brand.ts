/**
 * Brand assets for the submission, rendered from code (src/app/icon.svg):
 *   tsx scripts/brand.ts <out-dir>
 * writes logo-512.png (the mark) and wordmark-1200x630.png (mark and name on midnight).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { chromium } from "@playwright/test";

async function main(): Promise<void> {
  const out = process.argv[2];
  if (!out) throw new Error("usage: tsx scripts/brand.ts <out-dir>");
  const svg = readFileSync(join(__dirname, "../src/app/icon.svg"), "utf8");
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 512, height: 512 } });
    await page.setContent(
      `<html><body style="margin:0;background:transparent">${svg.replace("<svg ", '<svg width="512" height="512" ')}</body></html>`,
    );
    await page.screenshot({ path: join(out, "logo-512.png"), omitBackground: true });
    await page.setViewportSize({ width: 1200, height: 630 });
    await page.setContent(`<html><head>
      <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,500&display=block"><!-- hardcode-ok: the brand font for an offline render -->
      </head><body style="margin:0;width:1200px;height:630px;background:#0E1430;display:flex;align-items:center;justify-content:center;gap:48px">
      ${svg.replace("<svg ", '<svg width="200" height="200" ')}
      <span style="font-family:'Bodoni Moda',serif;font-weight:500;font-size:132px;color:#E7E3D8;letter-spacing:-0.01em">Afterhours</span>
      </body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: join(out, "wordmark-1200x630.png") });
  } finally {
    await browser.close();
  }
}

void main();
