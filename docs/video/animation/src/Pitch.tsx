/** The whole pitch: six scenes on pitch.md's timings, an ambient pad, optional voiceover. */
import React from "react";
import { AbsoluteFill, Audio, Loop, Sequence, getStaticFiles, interpolate, staticFile } from "remotion";

import { Captions } from "./Captions";
import { Claim } from "./scenes/Claim";
import { Close } from "./scenes/Close";
import { Hook } from "./scenes/Hook";
import { Market } from "./scenes/Market";
import { Night } from "./scenes/Night";
import { Product } from "./scenes/Product";
import { C, SCENES, TOTAL_SECONDS, sec } from "./theme";

const PARTS = [
  ["hook", Hook],
  ["product", Product],
  ["claim", Claim],
  ["night", Night],
  ["market", Market],
  ["close", Close],
] as const;

/** Your recording, if you put one in public/ as voiceover.mp3, .wav or .m4a. */
function voiceover(): string | null {
  const file = getStaticFiles().find((f) => /^voiceover\.(mp3|wav|m4a)$/.test(f.name));
  return file ? file.name : null;
}

export const Pitch: React.FC<{ captions: boolean }> = ({ captions }) => {
  const vo = voiceover();
  const total = sec(TOTAL_SECONDS);
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      {PARTS.map(([key, Scene]) => {
        const [a, b] = SCENES[key];
        return (
          <Sequence key={key} from={sec(a)} durationInFrames={sec(b - a)} name={key}>
            <Scene />
          </Sequence>
        );
      })}
      {/* The night pad under everything; quieter when a voiceover is present. */}
      <Loop durationInFrames={sec(24)}>
        <Audio
          src={staticFile("pad.wav")}
          volume={(f) => interpolate(f, [0, 30], [0, vo ? 0.08 : 0.18], { extrapolateRight: "clamp" })}
        />
      </Loop>
      {vo && <Audio src={staticFile(vo)} volume={1} />}
      {captions && <Captions />}
      <Sequence from={total - 1}>
        <AbsoluteFill style={{ background: C.bgDeep }} />
      </Sequence>
    </AbsoluteFill>
  );
};
