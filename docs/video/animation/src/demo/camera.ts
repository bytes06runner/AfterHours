/**
 * The auto-zoom camera. Every click and focus point in a recording's log asks for a zoom
 * (scale, centre, how long to hold); the camera follows those targets with a critically damped
 * spring, so it eases in, glides between nearby clicks and eases back out, like Screen Studio or
 * Recordly. Coordinates are the page's CSS pixels (1440 x 810).
 */
import { REC } from "./edit";

export const VIEW = { w: 1440, h: 810 };
const STEP = 1 / 120; // simulation step, seconds of recording time
const OMEGA = 5.2; // spring speed: about 0.6 s to settle
const LEAD = { click: 0.55, focus: 0.1 }; // start zooming this early (the cursor is on its way)

export type Cam = { s: number; x: number; y: number };

function clampCam({ s, x, y }: Cam): Cam {
  const hw = VIEW.w / (2 * s);
  const hh = VIEW.h / (2 * s);
  return { s, x: Math.min(VIEW.w - hw, Math.max(hw, x)), y: Math.min(VIEW.h - hh, Math.max(hh, y)) };
}

function target(rec: string, t: number): Cam {
  let best: { start: number; cam: Cam } | null = null;
  for (const e of REC[rec].events) {
    if ((e.type !== "click" && e.type !== "focus") || e.x === undefined || e.y === undefined) continue;
    const start = e.t - LEAD[e.type as "click" | "focus"];
    const end = e.t + (e.hold ?? 1.2);
    if (t >= start && t <= end && (!best || start > best.start)) {
      best = { start, cam: clampCam({ s: e.scale ?? 1.6, x: e.x, y: e.y }) };
    }
  }
  return best?.cam ?? { s: 1, x: VIEW.w / 2, y: VIEW.h / 2 };
}

const cache = new Map<string, Cam[]>();

/** The camera for every STEP of a recording, simulated once per recording. */
function path(rec: string): Cam[] {
  const hit = cache.get(rec);
  if (hit) return hit;
  const n = Math.ceil(REC[rec].duration / STEP) + 2;
  const out: Cam[] = [];
  // Scale is smoothed in log space so zooming in and out feel equally fast.
  let cur = { l: 0, x: VIEW.w / 2, y: VIEW.h / 2 };
  let vel = { l: 0, x: 0, y: 0 };
  for (let i = 0; i < n; i++) {
    const tg = target(rec, i * STEP);
    const goal = { l: Math.log(tg.s), x: tg.x, y: tg.y };
    for (const k of ["l", "x", "y"] as const) {
      const a = OMEGA * OMEGA * (goal[k] - cur[k]) - 2 * OMEGA * vel[k];
      vel[k] += a * STEP;
      cur[k] += vel[k] * STEP;
    }
    out.push(clampCam({ s: Math.max(1, Math.exp(cur.l)), x: cur.x, y: cur.y }));
  }
  cache.set(rec, out);
  return out;
}

export function camera(rec: string, t: number): Cam {
  const p = path(rec);
  const i = Math.max(0, Math.min(p.length - 1, t / STEP));
  const a = p[Math.floor(i)];
  const b = p[Math.min(p.length - 1, Math.floor(i) + 1)];
  const f = i - Math.floor(i);
  return { s: a.s + (b.s - a.s) * f, x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
}

/** The page URL showing at time t (the last navigation before it). */
export function urlAt(rec: string, t: number): string {
  const pages = REC[rec].events.filter((e) => e.type === "page" && e.url && e.url !== "about:blank");
  let url = pages[0]?.url ?? "";
  for (const e of pages) if (e.t <= t) url = e.url!;
  return url;
}
