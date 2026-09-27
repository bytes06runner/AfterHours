/** Timed subtitles for the voiceover guide: each line gets time in proportion to its words. */
import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

import { SCRIPT } from "./script";
import { C, FONT, SCENES, sec } from "./theme";

type Cue = { from: number; to: number; text: string };

const cues: Cue[] = (Object.keys(SCENES) as (keyof typeof SCENES)[]).flatMap((k) => {
  const [a, b] = SCENES[k];
  const lines = SCRIPT[k];
  const words = lines.map((l) => l.split(" ").length);
  const total = words.reduce((x, y) => x + y, 0);
  let t = a;
  return lines.map((text, i) => {
    const dur = ((b - a) * words[i]) / total;
    const cue = { from: sec(t), to: sec(t + dur), text };
    t += dur;
    return cue;
  });
});

export const Captions: React.FC = () => {
  const f = useCurrentFrame();
  const cue = cues.find((c) => f >= c.from && f < c.to);
  if (!cue) return null;
  const o = interpolate(f, [cue.from, cue.from + 6, cue.to - 6, cue.to], [0, 1, 1, 0]);
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 36 }}>
      <div
        style={{
          maxWidth: 1600,
          background: "rgba(7,10,28,0.82)",
          border: `2px solid ${C.rule}`,
          borderRadius: 16,
          padding: "14px 28px",
          fontFamily: FONT.sans,
          fontWeight: 600,
          fontSize: 34,
          color: C.text,
          textAlign: "center",
          opacity: o,
        }}
      >
        {cue.text}
      </div>
    </AbsoluteFill>
  );
};
