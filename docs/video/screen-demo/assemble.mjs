/**
 * Turns each recorded scene (out/<scene>/frames + frames.txt) into a constant 30 fps MP4 for the
 * Remotion edit, and gathers every scene's event log into one file the edit reads for its zooms.
 * Uses the ffmpeg that ships with Remotion, so nothing else needs installing.
 */
import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";

const OUT = new URL("./out/", import.meta.url).pathname;
const EDIT = new URL("../animation/", import.meta.url).pathname;
const CLIPS = `${EDIT}public/demo/`;
mkdirSync(CLIPS, { recursive: true });

const only = process.argv.slice(2);
const scenes = readdirSync(OUT).filter((d) => existsSync(`${OUT}${d}/frames.txt`)).sort();
const all = {};
for (const name of scenes) {
  const meta = JSON.parse(readFileSync(`${OUT}${name}/events.json`, "utf8"));
  all[name] = { ...meta, clip: `demo/${name}.mp4` };
  if (only.length && !only.some((o) => name.includes(o))) continue;
  execFileSync(
    `${EDIT}node_modules/.bin/remotion`,
    ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "frames.txt",
      "-fps_mode", "cfr", "-r", "30", "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
      "-movflags", "+faststart", `${CLIPS}${name}.mp4`],
    { cwd: `${OUT}${name}`, stdio: "inherit" },
  );
  console.log(`${name}.mp4  ${meta.duration}s`);
}
writeFileSync(`${EDIT}src/demo/recordings.generated.json`, JSON.stringify(all, null, 1) + "\n");
console.log(`wrote ${Object.keys(all).length} scenes to src/demo/recordings.generated.json`);
