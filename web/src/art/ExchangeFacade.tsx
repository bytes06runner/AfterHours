"use client";

/**
 * ExchangeFacade: an art deco exchange drawn in code, with sky, stars and a two-layer skyline.
 * Live data: the clock shows New York time, the bell swings on each session change, windows
 * light floor by floor as --phase rises, and skyline windows scale with vault activity.
 * Geometry sits on an 8 px grid inside a 1200 x 720 view box.
 */
import { memo } from "react";

import { newYorkClock } from "@/lib/time";

import "./art.css";

const W = 1200;
const H = 720;
/** Sky above the finial left out of the frame so the hero headline sits higher. */
const CROP_TOP = 24;

/** Small deterministic PRNG so the art is identical on server and client. */
function rng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

const STARS = (() => {
  const r = rng(7);
  return Array.from({ length: 56 }, () => ({ x: r() * W, y: r() * 300, r: r() < 0.2 ? 2 : 1.25 }));
})();

interface Tower {
  x: number;
  w: number;
  h: number;
  steps: number;
}

function towers(seed: number, count: number, minH: number, maxH: number): Tower[] {
  const r = rng(seed);
  const out: Tower[] = [];
  let x = -40;
  for (let i = 0; i < count && x < W; i++) {
    const w = 56 + Math.round(r() * 7) * 8;
    out.push({
      x,
      w,
      h: minH + Math.round((r() * (maxH - minH)) / 8) * 8,
      steps: 1 + Math.floor(r() * 3),
    });
    x += w + Math.round(r() * 2) * 8;
  }
  return out;
}

const FAR = towers(11, 24, 180, 360);
const NEAR = towers(23, 22, 120, 260);

function towerPath(t: Tower, ground: number): string {
  // Stepped silhouette: the full width rises to the first setback, then each step is 8 px
  // narrower per side and 24 px tall, up to the roof at ground - h.
  const top = ground - t.h;
  const shoulder = top + t.steps * 24;
  let d = `M${t.x} ${ground} V${shoulder}`;
  for (let s = 1; s <= t.steps; s++) d += ` H${t.x + s * 8} V${shoulder - s * 24}`;
  d += ` H${t.x + t.w - t.steps * 8}`;
  for (let s = t.steps - 1; s >= 0; s--) d += ` V${shoulder - s * 24} H${t.x + t.w - s * 8}`;
  return `${d} V${ground} Z`;
}

function SkylineLayer({
  layer,
  ground,
  activity,
  className,
}: {
  layer: Tower[];
  ground: number;
  activity: number;
  className: string;
}) {
  const r = rng(layer.length * 97);
  return (
    <g>
      {layer.map((t, i) => (
        <path key={i} d={towerPath(t, ground)} className={className} />
      ))}
      {layer.flatMap((t, i) => {
        const cols = Math.max(1, Math.floor((t.w - 24) / 16));
        const rows = Math.floor((t.h - t.steps * 24 - 24) / 24);
        const cells = [];
        for (let row = 0; row < rows; row++) {
          for (let c = 0; c < cols; c++) {
            // Activity decides how many windows can light at night.
            if (r() > 0.25 + 0.6 * activity) continue;
            cells.push(
              <rect
                key={`${i}-${row}-${c}`}
                x={t.x + 12 + c * 16}
                y={ground - 24 - row * 24 - 8}
                width={6}
                height={8}
                className="a-lit"
                style={{ "--floor": 1 + (row % 4) } as React.CSSProperties}
              />,
            );
          }
        }
        return cells;
      })}
    </g>
  );
}

/** The pediment bell. It swings once whenever `bells` increases. */
function Bell({ bells }: { bells: number }) {
  return (
    <g transform="translate(600 130)">
      <g key={bells} className={bells > 0 ? "a-bell ringing" : "a-bell"}>
        <line x1={0} y1={0} x2={0} y2={10} className="a-line-2" />
        <path
          d="M-16 34 C-16 16 -12 10 0 10 C12 10 16 16 16 34 L22 38 L-22 38 Z"
          className="a-brass"
        />
        <circle cx={0} cy={42} r={4} className="a-brass" />
      </g>
    </g>
  );
}

function Clock({ iso }: { iso: string | undefined }) {
  const { h, m } = newYorkClock(iso ?? new Date());
  const hourAngle = ((h % 12) + m / 60) * 30;
  const minuteAngle = m * 6;
  return (
    <g>
      <circle cx={600} cy={212} r={26} className="a-stone" />
      <circle cx={600} cy={212} r={26} className="a-line-2" />
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i * Math.PI) / 6;
        return (
          <line
            key={i}
            x1={600 + Math.sin(a) * 20}
            y1={212 - Math.cos(a) * 20}
            x2={600 + Math.sin(a) * 24}
            y2={212 - Math.cos(a) * 24}
            className="a-line"
          />
        );
      })}
      <line
        x1={600}
        y1={212}
        x2={600}
        y2={198}
        className="a-line-2 a-hand"
        style={{ transform: `rotate(${hourAngle}deg)`, transformOrigin: "600px 212px" }}
      />
      <line
        x1={600}
        y1={212}
        x2={600}
        y2={192}
        className="a-line a-hand"
        style={{ transform: `rotate(${minuteAngle}deg)`, transformOrigin: "600px 212px" }}
      />
      <circle cx={600} cy={212} r={2.5} className="a-brass" />
    </g>
  );
}

const LEFT_COLS = [225, 320, 415];
const COLS = [...LEFT_COLS, ...LEFT_COLS.map((x) => W - x - 34)];
const BAY_WINDOWS = [267, 362, ...[267, 362].map((x) => W - x - 45)];

function Facade({ bells, clockIso }: { bells: number; clockIso: string | undefined }) {
  const lit = (floor: number) => ({ "--floor": floor }) as React.CSSProperties;
  return (
    <g>
      {/* Stepped pediment and finial */}
      <line x1={600} y1={48} x2={600} y2={76} className="a-line-2" />
      <circle cx={600} cy={46} r={5} className="a-brass" />
      <rect x={580} y={76} width={40} height={14} className="a-stone-shade" />
      <rect x={560} y={90} width={80} height={14} className="a-stone" />
      <rect x={540} y={104} width={120} height={16} className="a-stone-shade" />
      {/* Crown with the bell arch */}
      <rect x={520} y={120} width={160} height={54} className="a-stone" />
      <path d="M570 172 V148 A30 30 0 0 1 630 148 V172 Z" className="a-glass" />
      <path d="M570 172 V148 A30 30 0 0 1 630 148 V172 Z" className="a-lit" style={lit(4)} />
      <Bell bells={bells} />
      <rect x={520} y={120} width={160} height={54} className="a-line" />
      {/* Third tier with the clock */}
      <rect x={370} y={174} width={460} height={8} className="a-stone-deep" />
      <rect x={380} y={182} width={440} height={62} className="a-stone" />
      {[405, 455, 505, 669, 719, 769].map((x) => (
        <g key={x}>
          <rect x={x} y={196} width={26} height={34} className="a-glass" />
          <rect x={x} y={196} width={26} height={34} className="a-lit" style={lit(3)} />
        </g>
      ))}
      <Clock iso={clockIso} />
      {/* Second tier */}
      <rect x={240} y={244} width={720} height={8} className="a-stone-deep" />
      <rect x={250} y={252} width={700} height={118} className="a-stone" />
      {[0, 1].map((row) =>
        Array.from({ length: 12 }, (_, i) => {
          const x = 285 + i * 55;
          const y = 268 + row * 50;
          // A few rooms stay dark at night.
          const dark = (i * 7 + row * 3) % 11 === 0;
          return (
            <g key={`${row}-${i}`}>
              <rect x={x} y={y} width={30} height={34} className="a-glass" />
              {!dark && (
                <rect x={x} y={y} width={30} height={34} className="a-lit" style={lit(2 - row)} />
              )}
            </g>
          );
        }),
      )}
      {/* Architrave (the ticker ribbon sits here) */}
      <rect x={170} y={370} width={860} height={30} className="a-stone-deep" />
      {/* Base block, bays and columns */}
      <rect x={190} y={400} width={820} height={236} className="a-stone" />
      {BAY_WINDOWS.map((x) => (
        <g key={x}>
          <rect x={x} y={440} width={45} height={160} className="a-glass" />
          <rect x={x} y={440} width={45} height={160} className="a-lit" style={lit(0.5)} />
          <line x1={x + 22.5} y1={440} x2={x + 22.5} y2={600} className="a-line" />
          <line x1={x} y1={520} x2={x + 45} y2={520} className="a-line" />
        </g>
      ))}
      {COLS.map((x) => (
        <g key={x}>
          <rect x={x - 4} y={408} width={42} height={10} className="a-stone-deep" />
          <rect x={x} y={418} width={34} height={198} className="a-stone-shade" />
          {[9, 17, 25].map((f) => (
            <line key={f} x1={x + f} y1={424} x2={x + f} y2={610} className="a-line" />
          ))}
          <rect x={x - 4} y={616} width={42} height={10} className="a-stone-deep" />
        </g>
      ))}
      {/* Sunburst fan over the doors */}
      <path d="M500 520 A100 100 0 0 1 700 520 Z" className="a-stone-shade" />
      <path d="M500 520 A100 100 0 0 1 700 520 Z" className="a-lit" style={lit(0.2)} />
      {Array.from({ length: 13 }, (_, i) => {
        const a = Math.PI - (i * Math.PI) / 12;
        return (
          <line
            key={i}
            x1={600 + Math.cos(a) * 28}
            y1={520 - Math.sin(a) * 28}
            x2={600 + Math.cos(a) * 100}
            y2={520 - Math.sin(a) * 100}
            className="a-brass-line"
          />
        );
      })}
      <path d="M500 520 A100 100 0 0 1 700 520" className="a-brass-line" />
      {/* Doors */}
      <rect x={540} y={528} width={120} height={108} className="a-glass" />
      <rect x={540} y={528} width={120} height={108} className="a-lit" style={lit(0.1)} />
      <line x1={600} y1={528} x2={600} y2={636} className="a-line-2" />
      <rect x={540} y={528} width={120} height={108} className="a-line-2" />
      {/* Steps and ground */}
      <rect x={180} y={636} width={840} height={18} className="a-stone-shade" />
      <rect x={160} y={654} width={880} height={18} className="a-stone" />
      <rect x={140} y={672} width={920} height={18} className="a-stone-shade" />
      <line x1={140} y1={690} x2={1060} y2={690} className="a-line" />
      <rect x={0} y={690} width={W} height={30} className="a-stone-deep" />
    </g>
  );
}

export interface ExchangeFacadeProps {
  bells: number;
  clockIso?: string;
  /** 0..1, how busy the vault is; more lit skyline windows at night. */
  activity?: number;
  ticker?: React.ReactNode;
  title?: string;
}

export const ExchangeFacade = memo(function ExchangeFacade({
  bells,
  clockIso,
  activity = 0.6,
  ticker,
  title = "An art deco stock exchange at the edge of a city skyline",
}: ExchangeFacadeProps) {
  const iso = clockIso;
  return (
    <svg
      viewBox={`0 ${CROP_TOP} ${W} ${H - CROP_TOP}`}
      role="img"
      aria-label={title}
      className="block h-auto w-full"
    >
      <rect x={0} y={0} width={W} height={H} className="a-sky-0" />
      <rect x={0} y={260} width={W} height={130} className="a-sky-1" />
      <rect x={0} y={390} width={W} height={130} className="a-sky-2" />
      <rect x={0} y={520} width={W} height={200} className="a-sky-3" />
      {STARS.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} className="a-star" />
      ))}
      <circle cx={980} cy={160} r={56} className="a-sun" />
      <g className="a-moon">
        <mask id="moon-cut">
          <rect x={150} y={90} width={140} height={140} fill="white" />
          <circle cx={238} cy={140} r={40} fill="black" />
        </mask>
        <circle cx={220} cy={150} r={40} mask="url(#moon-cut)" />
      </g>
      <SkylineLayer layer={FAR} ground={600} activity={activity * 0.8} className="a-far" />
      <SkylineLayer layer={NEAR} ground={690} activity={activity} className="a-near" />
      <Facade bells={bells} clockIso={iso} />
      {ticker && (
        <foreignObject x={170} y={370} width={860} height={30}>
          {ticker}
        </foreignObject>
      )}
    </svg>
  );
});
