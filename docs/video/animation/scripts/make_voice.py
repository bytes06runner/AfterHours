"""Generate the AI voiceover with Kokoro-82M (Apache 2.0, runs locally, no account).

Reads voiceover.json, fills {key} from artifacts/report/numbers.json, speaks each cue into
public/vo/NN.wav, and writes src/vo.generated.json (start, length, words) for the video: the
audio is placed at each cue and the subtitles show exactly what is said. A cue that would run
into the next one is regenerated slightly faster, up to max_speed; beyond that the script stops.

Run through `npm run voice` (it uses the .tts virtual environment).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
from kokoro import KPipeline  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent.parent.parent
RATE = 24000  # Kokoro's output sample rate
GAP = 0.25  # seconds of air kept before the next cue
END = 145.0  # the video's length (theme.ts TOTAL_SECONDS)


def fill(text: str, numbers: dict[str, dict[str, str]]) -> str:
    def one(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in numbers:
            sys.exit(f"voiceover.json uses {{{key}}}, which numbers.json does not have")
        return numbers[key]["text"]

    return re.sub(r"\{([\w.]+)\}", one, text)


def speak(pipe: KPipeline, text: str, voice: str, speed: float) -> np.ndarray:
    parts = [a.numpy() for _, _, a in pipe(text, voice=voice, speed=speed)]
    return np.concatenate(parts) if parts else np.zeros(1)


def main() -> None:
    doc = json.loads((HERE / "voiceover.json").read_text())
    numbers = json.loads((ROOT / "artifacts" / "report" / "numbers.json").read_text())["numbers"]
    voice, max_speed = doc["voice"], float(doc["max_speed"])
    cues = doc["cues"]
    out = HERE / "public" / "vo"
    out.mkdir(parents=True, exist_ok=True)
    for old in [*out.glob("*.wav"), *out.glob("*.mp3")]:
        old.unlink()
    pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    made, problems = [], []
    for i, cue in enumerate(cues):
        text = fill(cue["text"], numbers)
        start = float(cue["at"])
        room = (float(cues[i + 1]["at"]) if i + 1 < len(cues) else END) - start - GAP
        speed = 1.0
        audio = speak(pipe, text, voice, speed)
        length = len(audio) / RATE
        while length > room and speed < max_speed:  # speed up in small steps until it fits
            speed = min(max_speed, max(speed + 0.03, length / room * speed * 1.02))
            audio = speak(pipe, text, voice, speed)
            length = len(audio) / RATE
        if length > room:
            problems.append(f"cue {i} at {start}s needs {length:.1f}s, has {room:.1f}s: {text}")
        wav, name = out / f"{i:02d}.wav", f"{i:02d}.mp3"
        sf.write(wav, audio, RATE)
        # MP3 through Remotion's bundled ffmpeg: small enough to commit, so a fresh clone renders
        # the same video without installing the voice model.
        subprocess.run(
            [
                "npx",
                "remotion",
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-i",
                str(wav),
                "-b:a",
                "160k",
                str(out / name),
            ],
            cwd=HERE,
            check=True,
        )
        wav.unlink()
        made.append({"file": f"vo/{name}", "at": start, "seconds": round(length, 3), "text": text})
        print(
            f"{i:02d} at {start:6.1f}s  {length:4.1f}s of {room:4.1f}s  "
            f"speed {speed:.2f}  {text[:60]}"
        )
    if problems:
        sys.exit("Some lines do not fit; shorten them in voiceover.json:\n" + "\n".join(problems))
    (HERE / "src" / "vo.generated.json").write_text(
        json.dumps({"voice": voice, "cues": made}, indent=2) + "\n"
    )
    print(f"wrote {len(made)} clips to public/vo and src/vo.generated.json")


if __name__ == "__main__":
    main()
