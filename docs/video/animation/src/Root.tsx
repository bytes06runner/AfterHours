import React from "react";
import { Composition } from "remotion";

import { Pitch } from "./Pitch";
import { FPS, H, TOTAL_SECONDS, W, sec } from "./theme";

export const Root: React.FC = () => (
  <>
    <Composition id="Pitch" component={Pitch} defaultProps={{ captions: false }} durationInFrames={sec(TOTAL_SECONDS)} fps={FPS} width={W} height={H} />
    <Composition id="PitchWithScript" component={Pitch} defaultProps={{ captions: true }} durationInFrames={sec(TOTAL_SECONDS)} fps={FPS} width={W} height={H} />
  </>
);
