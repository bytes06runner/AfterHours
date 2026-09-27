/** 2:05 to 2:25. The close: the bell, the name, where to find it, and the team's own words. */
import React from "react";
import { AbsoluteFill, Sequence, interpolate, useCurrentFrame } from "remotion";

import { Sfx } from "../components/Sfx";
import { Grain, Moon, Skyline, Sky, Stars, Vignette } from "../components/Atmosphere";
import { Exchange, Kinetic, Sunburst } from "../components/Pieces";
import team from "../team.json";
import { C, FONT } from "../theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Close: React.FC = () => {
  const f = useCurrentFrame();
  const out = interpolate(f, [560, 600], [1, 0], clamp);
  const lift = interpolate(f, [0, 120], [80, 0], clamp);
  return (
    <AbsoluteFill style={{ background: C.bgDeep, opacity: out }}>
      <Sky />
      <Stars />
      <Moon x={58} y={9} size={110} />
      <AbsoluteFill style={{ transform: `translateY(${lift}px)` }}>
        <Skyline />
        <div style={{ position: "absolute", left: 1080, bottom: 0, transform: "scale(0.9)", transformOrigin: "bottom" }}>
          <Exchange ringAt={20} lights={1} />
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{ padding: "130px 130px" }}>
        <div style={{ position: "relative", width: 900 }}>
          <Sunburst size={1100} opacity={interpolate(f, [20, 60], [0, 0.4], clamp)} />
          <div style={{ fontFamily: FONT.display, fontSize: 170, color: C.text, position: "relative", opacity: interpolate(f, [20, 40], [0, 1], clamp) }}>
            Afterhours
          </div>
        </div>
        <Kinetic text="Lend through the night." at={50} size={72} color={C.brass} />
        {team.who && (
          <div style={{ marginTop: 40, maxWidth: 900 }}>
            <Kinetic text={team.who} at={110} size={40} display={false} weight={600} stagger={1} />
          </div>
        )}
        {team.ask && (
          <div style={{ marginTop: 24, maxWidth: 900 }}>
            <Kinetic text={team.ask} at={170} size={40} display={false} weight={800} stagger={1} color={C.brass} />
          </div>
        )}
        <div style={{ marginTop: 44, fontFamily: FONT.sans, fontWeight: 800, fontSize: 40, color: C.text, opacity: interpolate(f, [90, 110], [0, 1], clamp), lineHeight: 1.55, background: "rgba(7,10,28,0.6)", padding: "18px 26px", borderRadius: 18, display: "inline-block" }}>
          <div>{team.site}</div>
          <div style={{ fontWeight: 600, fontSize: 32, opacity: 0.85 }}>{team.repo}</div>
          <div style={{ fontWeight: 600, fontSize: 26, color: C.brass, letterSpacing: 2, textTransform: "uppercase", marginTop: 8 }}>
            Built on Robinhood Chain · Morpho
          </div>
        </div>
      </AbsoluteFill>
      <Sequence from={20}>
        <Sfx name="bell" volume={0.9} />
      </Sequence>
      <Sequence from={430}>
        <Sfx name="bell" volume={0.7} />
      </Sequence>
      <Grain />
      <Vignette />
    </AbsoluteFill>
  );
};
