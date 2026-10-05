import React from "react";
import { Composition } from "remotion";

import { Demo } from "./demo/Demo";
import { timeline } from "./demo/edit";
import { Pitch } from "./Pitch";
import { Week3, week3Timeline } from "./week3/Week3";
import { FPS, H, TOTAL_SECONDS, W, sec } from "./theme";

export const Root: React.FC = () => (
  <>
    <Composition id="Pitch" component={Pitch} defaultProps={{ captions: false }} durationInFrames={sec(TOTAL_SECONDS)} fps={FPS} width={W} height={H} />
    <Composition id="PitchWithScript" component={Pitch} defaultProps={{ captions: true }} durationInFrames={sec(TOTAL_SECONDS)} fps={FPS} width={W} height={H} />
    <Composition id="ScreenDemo" component={Demo} defaultProps={{ sfx: true }} durationInFrames={timeline().total} fps={FPS} width={W} height={H} />
    <Composition id="ScreenDemoSilent" component={Demo} defaultProps={{ sfx: false }} durationInFrames={timeline().total} fps={FPS} width={W} height={H} />
    <Composition id="Week3" component={Week3} durationInFrames={week3Timeline().total} fps={FPS} width={W} height={H} />
  </>
);
