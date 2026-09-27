/** The whole pitch: six scenes on pitch.md's timings, an ambient pad, optional voiceover. */
import React from "react";
import { AbsoluteFill, Audio, Loop, Sequence, getStaticFiles, interpolate, staticFile } from "remotion";

import { Captions } from "./Captions";
import { SfxGain } from "./components/Sfx";
import { Claim } from "./scenes/Claim";
import { Close } from "./scenes/Close";
import { Hook } from "./scenes/Hook";
import { Market } from "./scenes/Market";
import { Night } from "./scenes/Night";
import { Product } from "./scenes/Product";
import { C, SCENES, TOTAL_SECONDS, sec } from "./theme";
import vo from "./vo.generated.json";

const PARTS = [
  ["hook", Hook],
  ["product", Product],
  ["claim", Claim],
  ["night", Night],
  ["market", Market],
  ["close", Close],
] as const;

/** The AI voiceover cues (scripts/make_voice.py), unless you recorded your own. */
export const AI_CUES: { file: string; at: number; seconds: number; text: string }[] = vo.cues;

/** Your recording, if you put one in public/ as voiceover.mp3, .wav or .m4a. */
function voiceover(): string | null {
  const file = getStaticFiles().find((f) => /^voiceover\.(mp3|wav|m4a)$/.test(f.name));
  return file ? file.name : null;
}

export const Pitch: React.FC<{ captions: boolean }> = ({ captions }) => {
  const own = voiceover();
  const ai = own ? [] : AI_CUES;
  const speaking = Boolean(own) || ai.length > 0;
  const total = sec(TOTAL_SECONDS);
  return (
    <AbsoluteFill style={{ background: C.bgDeep }}>
      <SfxGain.Provider value={speaking ? 0.45 : 1}>
        {PARTS.map(([key, Scene]) => {
          const [a, b] = SCENES[key];
          return (
            <Sequence key={key} from={sec(a)} durationInFrames={sec(b - a)} name={key}>
              <Scene />
            </Sequence>
          );
        })}
      </SfxGain.Provider>
      {/* The night pad under everything; quieter under a voice. */}
      <Loop durationInFrames={sec(24)}>
        <Audio
          src={staticFile("pad.wav")}
          volume={(f) => interpolate(f, [0, 30], [0, speaking ? 0.07 : 0.18], { extrapolateRight: "clamp" })}
        />
      </Loop>
      {own && <Audio src={staticFile(own)} volume={1} />}
      {ai.map((c) => (
        <Sequence key={c.file} from={sec(c.at)} durationInFrames={sec(c.seconds) + 2} name={`vo ${c.text.slice(0, 24)}`}>
          <Audio src={staticFile(c.file)} volume={1} />
        </Sequence>
      ))}
      {captions && <Captions spoken={ai} />}
      <Sequence from={total - 1}>
        <AbsoluteFill style={{ background: C.bgDeep }} />
      </Sequence>
    </AbsoluteFill>
  );
};
