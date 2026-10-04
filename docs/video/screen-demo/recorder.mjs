/**
 * Records real sessions on the site for the demo video: a Chromium window at 1440 x 810 CSS
 * pixels rendered at 2x (2880 x 1620 frames, so zoomed shots stay sharp), a visible cursor with
 * click ripples, human-like mouse paths, and an event log (clicks, focus points, pages) that the
 * Remotion edit uses for its zooms. Every click is a real click on the real site.
 */
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../../web/package.json", import.meta.url));
const { chromium } = require("@playwright/test");

export const VIEW = { width: 1440, height: 810 };
export const SCALE = 2;

/** The cursor and click ripple, drawn in the page so they are part of every frame. */
function cursorScript() {
  const KEY = "__demo_cursor";
  const saved = (sessionStorage.getItem(KEY) || "720,405").split(",").map(Number);
  let x = saved[0], y = saved[1];
  const css = `
    #__cur{position:fixed;left:0;top:0;z-index:2147483647;pointer-events:none;
      filter:drop-shadow(0 2px 4px rgba(0,0,0,.45));transition:transform .08s ease-out}
    #__cur.down svg{transform:scale(.86);transform-origin:4px 2px}
    .__rip{position:fixed;z-index:2147483646;pointer-events:none;width:44px;height:44px;
      margin:-22px 0 0 -22px;border-radius:50%;border:3px solid #F1C76B;
      box-shadow:0 0 18px #F1C76Baa;animation:__rip .55s ease-out forwards}
    @keyframes __rip{from{transform:scale(.2);opacity:1}to{transform:scale(1.9);opacity:0}}`;
  const make = () => {
    if (document.getElementById("__cur")) return;
    const st = document.createElement("style");
    st.textContent = css;
    document.documentElement.appendChild(st);
    const c = document.createElement("div");
    c.id = "__cur";
    c.innerHTML =
      '<svg width="30" height="30" viewBox="0 0 28 28"><path d="M4 2 L4 22.5 L9.4 17.4 L13 25.4 L16.8 23.8 L13.3 16 L20.8 16 Z" fill="#fff" stroke="#0E1430" stroke-width="1.7" stroke-linejoin="round"/></svg>';
    c.style.transform = `translate(${x - 4}px, ${y - 2}px)`;
    document.documentElement.appendChild(c);
  };
  const place = () => {
    const c = document.getElementById("__cur");
    if (c) c.style.transform = `translate(${x - 4}px, ${y - 2}px)`;
    sessionStorage.setItem(KEY, `${x},${y}`);
  };
  addEventListener("mousemove", (e) => { x = e.clientX; y = e.clientY; make(); place(); }, { capture: true, passive: true });
  addEventListener("mousedown", (e) => {
    make();
    document.getElementById("__cur")?.classList.add("down");
    const r = document.createElement("div");
    r.className = "__rip";
    r.style.left = `${e.clientX}px`;
    r.style.top = `${e.clientY}px`;
    document.documentElement.appendChild(r);
    setTimeout(() => r.remove(), 700);
  }, { capture: true });
  addEventListener("mouseup", () => document.getElementById("__cur")?.classList.remove("down"), { capture: true });
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", make);
  else make();
}

export class Session {
  static async open({ welcomed = true } = {}) {
    // Without this flag the screencast sends 1x frames even with deviceScaleFactor 2.
    const browser = await chromium.launch({ args: [`--force-device-scale-factor=${SCALE}`] });
    const ctx = await browser.newContext({ viewport: VIEW, deviceScaleFactor: SCALE });
    await ctx.addInitScript(cursorScript);
    if (welcomed) await ctx.addInitScript(() => sessionStorage.setItem("ah:welcomed", "1"));
    const page = await ctx.newPage();
    const s = new Session(browser, ctx, page);
    s.cdp = await ctx.newCDPSession(page);
    // Client-side navigation (nav links) changes the URL without a goto; the edit's URL bar needs it.
    page.on("framenavigated", (f) => {
      if (f === page.mainFrame() && f.url() !== s.lastUrl) s.log("page", { url: f.url() });
    });
    return s;
  }

  constructor(browser, ctx, page) {
    this.browser = browser;
    this.ctx = ctx;
    this.page = page;
    this.pos = { x: VIEW.width / 2, y: VIEW.height / 2 };
  }

  /** Start capturing frames into out/<name>/. */
  async start(name, { top = true } = {}) {
    if (top) await this.page.evaluate(() => scrollTo(0, 0)); // the Simulation banner in view
    this.name = name;
    this.dir = new URL(`./out/${name}/`, import.meta.url).pathname;
    rmSync(this.dir, { recursive: true, force: true });
    mkdirSync(`${this.dir}frames`, { recursive: true });
    this.frames = [];
    this.events = [];
    this.t0 = Date.now() / 1000;
    this.cdp.on("Page.screencastFrame", async (f) => {
      const i = this.frames.length;
      writeFileSync(`${this.dir}frames/${String(i).padStart(6, "0")}.jpg`, Buffer.from(f.data, "base64"));
      this.frames.push(f.metadata.timestamp);
      await this.cdp.send("Page.screencastFrameAck", { sessionId: f.sessionId }).catch(() => {});
    });
    await this.cdp.send("Page.startScreencast", {
      format: "jpeg",
      quality: 92,
      maxWidth: VIEW.width * SCALE,
      maxHeight: VIEW.height * SCALE,
      everyNthFrame: 1,
    });
    this.log("page", { url: this.page.url() });
  }

  log(type, data = {}) {
    if (type === "page") this.lastUrl = data.url;
    if (!this.events) return; // before start(): warm-up navigation, not recorded
    this.events.push({ t: +(Date.now() / 1000 - this.t0).toFixed(3), type, ...data });
  }

  /** A focus point for the edit: zoom to (x, y) at `scale` for `hold` seconds. */
  focus(x, y, scale = 1.6, hold = 2.0) {
    this.log("focus", { x, y, scale, hold });
  }

  async stop() {
    await this.cdp.send("Page.stopScreencast");
    await this.page.waitForTimeout(300);
    const end = Date.now() / 1000;
    const times = this.frames;
    // ffmpeg concat list: each frame shown until the next one arrived.
    const lines = times.map((t, i) => {
      const next = i + 1 < times.length ? times[i + 1] : end;
      return `file 'frames/${String(i).padStart(6, "0")}.jpg'\nduration ${Math.max(0.001, next - t).toFixed(4)}`;
    });
    lines.push(`file 'frames/${String(times.length - 1).padStart(6, "0")}.jpg'`);
    writeFileSync(`${this.dir}frames.txt`, lines.join("\n") + "\n");
    // Event times are relative to t0; the first frame may arrive a moment later.
    const offset = times.length ? times[0] - this.t0 : 0;
    const events = this.events.map((e) => ({ ...e, t: +(e.t - offset).toFixed(3) }));
    writeFileSync(`${this.dir}events.json`, JSON.stringify({ name: this.name, view: VIEW, scale: SCALE, duration: +(end - times[0]).toFixed(3), events }, null, 1));
    this.cdp.removeAllListeners("Page.screencastFrame");
    this.events = undefined;
    console.log(`${this.name}: ${times.length} frames, ${(end - times[0]).toFixed(1)} s, ${events.length} events`);
  }

  async close() {
    await this.browser.close();
  }

  // ------------------------------------------------------------------ human-like input
  async moveTo(x, y, { speed = 1 } = {}) {
    const { x: x0, y: y0 } = this.pos;
    const dist = Math.hypot(x - x0, y - y0);
    if (dist < 1) return;
    const ms = Math.min(1100, 260 + dist * 0.55) / speed;
    const steps = Math.max(8, Math.round(ms / 14));
    // A gentle curve: control point pushed sideways from the straight line.
    const side = (Math.sin(x0 * 0.13 + y * 0.07) > 0 ? 1 : -1) * Math.min(80, dist * 0.12);
    const cx = (x0 + x) / 2 + ((y - y0) / dist) * side;
    const cy = (y0 + y) / 2 - ((x - x0) / dist) * side;
    for (let i = 1; i <= steps; i++) {
      const t = i / steps;
      const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      const px = (1 - e) * (1 - e) * x0 + 2 * (1 - e) * e * cx + e * e * x;
      const py = (1 - e) * (1 - e) * y0 + 2 * (1 - e) * e * cy + e * e * y;
      await this.page.mouse.move(px, py);
      await this.page.waitForTimeout(ms / steps);
    }
    this.pos = { x, y };
  }

  async centerOf(locator) {
    await locator.waitFor({ state: "visible", timeout: 90_000 });
    await locator.scrollIntoViewIfNeeded();
    const b = await locator.boundingBox();
    return { x: b.x + b.width / 2, y: b.y + b.height / 2, box: b };
  }

  async hover(locator, pause = 400) {
    const { x, y } = await this.centerOf(locator);
    await this.moveTo(x, y);
    await this.page.waitForTimeout(pause);
    return { x, y };
  }

  /** Move to the element, pause like a person, and click it for real. */
  async click(locator, { zoom = 1.7, hold = 1.3, after = 700 } = {}) {
    const { x, y } = await this.centerOf(locator);
    await this.moveTo(x, y);
    await this.page.waitForTimeout(160);
    this.log("click", { x: +x.toFixed(1), y: +y.toFixed(1), scale: zoom, hold });
    await this.page.mouse.down();
    await this.page.waitForTimeout(70);
    await this.page.mouse.up();
    await this.page.waitForTimeout(after);
    return { x, y };
  }

  async type(text, delay = 90) {
    await this.page.keyboard.type(text, { delay });
  }

  /** Smooth scroll by `dy` CSS pixels over `ms` (eased, like a trackpad). */
  async scroll(dy, ms = 1200) {
    this.log("scroll", { dy });
    await this.page.evaluate(
      ([dy, ms]) =>
        new Promise((done) => {
          const y0 = scrollY, t0 = performance.now();
          const step = (now) => {
            const t = Math.min(1, (now - t0) / ms);
            const e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
            scrollTo(0, y0 + dy * e);
            if (t < 1) requestAnimationFrame(step);
            else done();
          };
          requestAnimationFrame(step);
        }),
      [dy, ms],
    );
  }

  async wait(ms) {
    await this.page.waitForTimeout(ms);
  }

  async goto(url, opts = {}) {
    await this.page.goto(url, { waitUntil: "domcontentloaded", ...opts }); // logged by framenavigated
  }
}
