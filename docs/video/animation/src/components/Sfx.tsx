/** Sound effects that step back when a voice is speaking (the gain comes from Pitch). */
import React, { createContext, useContext } from "react";
import { Audio, staticFile } from "remotion";

export const SfxGain = createContext(1);

export const Sfx: React.FC<{ name: string; volume?: number }> = ({ name, volume = 1 }) => {
  const gain = useContext(SfxGain);
  return <Audio src={staticFile(`${name}.wav`)} volume={volume * gain} />;
};
