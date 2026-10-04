/**
 * The screen demo's cut: which part of each real recording is used, where waiting is sped up,
 * how scenes are grouped into chapters, and how each one is labelled. The recordings and their
 * click/focus logs come from docs/video/screen-demo (recordings.generated.json).
 */
import recordings from "./recordings.generated.json";

export type Env = "live" | "site" | "sim" | "testnet" | "history" | "agents";

/** The honest label shown in the window's toolbar for each kind of footage. */
export const ENV: Record<Env, { label: string; tone: "safe" | "brass" | "frost" }> = {
  site: { label: "Live site · the vault is a simulation", tone: "brass" },
  live: { label: "Live · Robinhood Chain mainnet, read-only", tone: "safe" },
  sim: { label: "Simulation · local chain", tone: "brass" },
  testnet: { label: "Robinhood Chain Testnet", tone: "frost" },
  history: { label: "Historical prices · simulated vault", tone: "frost" },
  agents: { label: "Live site · read-only tools, nothing can trade", tone: "safe" },
};

type Rec = {
  clip: string;
  duration: number;
  events: { t: number; type: string; x?: number; y?: number; scale?: number; hold?: number; url?: string }[];
};
export const REC = recordings as unknown as Record<string, Rec>;

export type Shot = {
  rec: string;
  env: Env;
  from: number; // seconds into the recording
  to: number;
  /** Stretches where nothing happens but waiting on the network, played faster (and marked so). */
  fast?: { from: number; to: number; speed: number; note: string }[];
};

export type Chapter = { n: string; title: string; line: string; env: Env; shots: Shot[] };

export const CHAPTERS: Chapter[] = [
  {
    n: "01",
    title: "The front door",
    line: "What happens to a lending market when the stock exchange closes.",
    env: "site",
    shots: [{ rec: "01-landing", env: "site", from: 3.4, to: 24.0 }],
  },
  {
    n: "02",
    title: "Frozen today, thin tomorrow",
    line: "Every Stock Token's price regime and price quality, read live from Robinhood Chain mainnet.",
    env: "live",
    shots: [
      { rec: "10-regimes", env: "live", from: 0.0, to: 48.0, fast: [{ from: 15.2, to: 35.4, speed: 8, note: "loading the live risk board" }] },
      { rec: "03-checker", env: "live", from: 0.2, to: 29.0, fast: [{ from: 5.0, to: 19.3, speed: 7, note: "reading the borrower's positions on mainnet" }] },
    ],
  },
  {
    n: "03",
    title: "A night in the vault",
    line: "Deposit, ring the closing bell, and watch the vault pull money back before the gap.",
    env: "sim",
    shots: [
      { rec: "04-deposit", env: "sim", from: 2.0, to: 22.4 },
      { rec: "05-closingbell", env: "sim", from: 0.0, to: 13.3 },
      { rec: "06-ledger", env: "sim", from: 0.0, to: 11.6 },
    ],
  },
  {
    n: "04",
    title: "Every move, provable onchain",
    line: "The bot's reasons on Robinhood Chain Testnet, checked in the browser and on the explorer.",
    env: "testnet",
    shots: [{ rec: "07-testnet", env: "testnet", from: 0.0, to: 15.0, fast: [{ from: 8.8, to: 11.8, speed: 3, note: "opening the block explorer" }] }],
  },
  {
    n: "05",
    title: "For agents",
    line: "The same risk as four read-only MCP tools any AI agent can call. They read; they cannot trade.",
    env: "agents",
    shots: [{ rec: "11-agents", env: "agents", from: 0.0, to: 19.6 }],
  },
  {
    n: "06",
    title: "The evidence",
    line: "The report card, with the test we wrote down before running it.",
    env: "history",
    shots: [{ rec: "09-report", env: "history", from: 0.6, to: 11.0 }],
  },
];

export const FPS = 30;
export const INTRO = 150; // frames
export const OUTRO = 210;
export const CARD = 60; // a chapter card, before the window comes in
export const XFADE = 12; // frames two shots overlap by

/** A shot cut into constant-speed pieces, each mapped to output frames. */
export type Piece = { from: number; to: number; speed: number; note?: string; start: number; frames: number };

export function pieces(shot: Shot): Piece[] {
  const out: Piece[] = [];
  let t = shot.from;
  let start = 0;
  const push = (from: number, to: number, speed: number, note?: string) => {
    if (to - from < 1 / FPS) return;
    const frames = Math.round(((to - from) * FPS) / speed);
    out.push({ from, to, speed, note, start, frames });
    start += frames;
  };
  for (const f of [...(shot.fast ?? [])].sort((a, b) => a.from - b.from)) {
    push(t, f.from, 1);
    push(f.from, f.to, f.speed, f.note);
    t = f.to;
  }
  push(t, shot.to, 1);
  return out;
}

export const shotFrames = (shot: Shot) => pieces(shot).reduce((a, p) => a + p.frames, 0);

/** Output frame (within the shot) to recording time, and back. */
export function clipTime(shot: Shot, frame: number): { t: number; piece: Piece } {
  const ps = pieces(shot);
  const piece = ps.find((p) => frame < p.start + p.frames) ?? ps[ps.length - 1];
  return { t: piece.from + ((frame - piece.start) / FPS) * piece.speed, piece };
}

export function outFrame(shot: Shot, t: number): number | null {
  for (const p of pieces(shot)) if (t >= p.from && t < p.to) return p.start + Math.round(((t - p.from) * FPS) / p.speed);
  return null;
}

/** The whole timeline: where each chapter card and shot starts, in output frames. */
export function timeline() {
  let at = INTRO;
  const chapters = CHAPTERS.map((ch) => {
    const card = at;
    at += CARD;
    const shots = ch.shots.map((shot, i) => {
      const start = i === 0 ? at : at - XFADE;
      const frames = shotFrames(shot);
      at = start + frames;
      return { shot, start, frames };
    });
    return { ch, card, shots };
  });
  return { chapters, outro: at, total: at + OUTRO };
}
