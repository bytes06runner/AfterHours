import { loadFont as loadDisplay } from "@remotion/google-fonts/BodoniModa";
import { loadFont as loadSans } from "@remotion/google-fonts/HankenGrotesk";

/** The web app's night palette (web/src/app/globals.css, --night-*), plus two accents. */
export const C = {
  bg: "#0e1430",
  bgDeep: "#070a1c",
  surface: "#1b2450",
  text: "#e7e3d8",
  brass: "#f1c76b",
  brassDeep: "#b98a2c",
  safe: "#62ad9f",
  risk: "#e2705f",
  rule: "#34407a",
  frost: "#9fb4ff",
};

export const FONT = {
  display: loadDisplay("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily,
  sans: loadSans("normal", { weights: ["400", "600", "800"], subsets: ["latin"] }).fontFamily,
};

export const FPS = 30;
export const W = 1920;
export const H = 1080;

/** Scene boundaries in seconds, from docs/video/pitch.md ("0:00 to 0:20" and so on). */
export const SCENES = {
  hook: [0, 20],
  product: [20, 50],
  claim: [50, 80],
  night: [80, 100],
  market: [100, 125],
  close: [125, 145],
} as const;

export const TOTAL_SECONDS = SCENES.close[1];

export const sec = (s: number) => Math.round(s * FPS);
