"""Synthesise the video's sound effects into public/ (no samples, no licences to worry about).

bell.wav   the closing bell: inharmonic bell partials with long decays
whoosh.wav a filtered noise sweep for transitions
tick.wav   a short clock tick
boom.wav   a low impact for the price gap
stamp.wav  a short thud for the hash landing onchain
pad.wav    a quiet ambient night pad, looped under the whole video
click.wav  a soft mouse click (press and release) for the screen demo
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path

RATE = 44100
OUT = Path(__file__).resolve().parent.parent / "public"


def write(name: str, samples: list[float], gain: float = 0.9) -> None:
    peak = max(1e-9, *(abs(s) for s in samples))
    scale = gain / peak
    OUT.mkdir(exist_ok=True)
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", int(s * scale * 32767)) for s in samples))


def bell(seconds: float = 5.5, base: float = 311.0) -> list[float]:
    # Church-bell partial ratios (hum, prime, tierce, quint, nominal, ...) with their own decays.
    partials = [
        (0.5, 1.0, 2.2),
        (1.0, 0.8, 1.6),
        (1.19, 0.55, 1.2),
        (1.5, 0.35, 1.0),
        (2.0, 0.6, 0.9),
        (2.51, 0.25, 0.6),
        (3.0, 0.2, 0.5),
        (4.07, 0.12, 0.35),
    ]
    n = int(seconds * RATE)
    out = []
    rng = random.Random(7)
    for i in range(n):
        t = i / RATE
        s = sum(
            a * math.exp(-t / d) * math.sin(2 * math.pi * base * r * t + r) for r, a, d in partials
        )
        if t < 0.012:  # the clapper strike
            s += (rng.random() * 2 - 1) * 0.6 * (1 - t / 0.012)
        out.append(s)
    return out


def whoosh(seconds: float = 1.1) -> list[float]:
    n = int(seconds * RATE)
    rng = random.Random(3)
    out, lp = [], 0.0
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) ** 2
        cutoff = 0.02 + 0.25 * t  # the sweep opens up
        lp += cutoff * ((rng.random() * 2 - 1) - lp)
        out.append(lp * env)
    return out


def tick(seconds: float = 0.08) -> list[float]:
    n = int(seconds * RATE)
    return [
        math.sin(2 * math.pi * 2200 * i / RATE) * math.exp(-i / (RATE * 0.008)) for i in range(n)
    ]


def click(seconds: float = 0.12) -> list[float]:
    # Two short, band-limited transients: the button going down, then coming back up.
    n = int(seconds * RATE)
    rng = random.Random(11)
    out, lp, hp_prev, prev = [], 0.0, 0.0, 0.0
    for i in range(n):
        t = i / RATE
        noise = rng.random() * 2 - 1
        env = math.exp(-t / 0.0035) + 0.55 * math.exp(-max(0.0, t - 0.07) / 0.003) * (t >= 0.07)
        lp += 0.35 * (noise - lp)  # soften the top end
        hp = lp - prev + 0.97 * hp_prev  # and drop the rumble
        prev, hp_prev = lp, hp
        out.append((hp + 0.4 * math.sin(2 * math.pi * 1800 * t)) * env)
    return out


def boom(seconds: float = 1.6) -> list[float]:
    n = int(seconds * RATE)
    rng = random.Random(5)
    out = []
    for i in range(n):
        t = i / RATE
        f = 70 * math.exp(-t * 2.5) + 38
        s = math.sin(2 * math.pi * f * t) * math.exp(-t * 2.2)
        s += (rng.random() * 2 - 1) * 0.25 * math.exp(-t * 18)
        out.append(s)
    return out


def stamp(seconds: float = 0.35) -> list[float]:
    n = int(seconds * RATE)
    rng = random.Random(9)
    return [
        (math.sin(2 * math.pi * 120 * i / RATE) * 0.9 + (rng.random() * 2 - 1) * 0.4)
        * math.exp(-i / (RATE * 0.05))
        for i in range(n)
    ]


def pad(seconds: float = 24.0) -> list[float]:
    # A slow minor-ninth chord with a gentle swell; loops cleanly (whole cycles of the swell).
    notes = [110.0, 164.81, 196.0, 246.94, 329.63]
    n = int(seconds * RATE)
    out = []
    for i in range(n):
        t = i / RATE
        swell = 0.6 + 0.4 * math.sin(2 * math.pi * t / seconds)
        s = sum(
            math.sin(2 * math.pi * f * t + k) * (0.5 + 0.5 * math.sin(2 * math.pi * t / (6 + k)))
            for k, f in enumerate(notes)
        )
        out.append(s * swell)
    return out


if __name__ == "__main__":
    write("bell.wav", bell())
    write("whoosh.wav", whoosh(), 0.7)
    write("tick.wav", tick(), 0.5)
    write("boom.wav", boom())
    write("stamp.wav", stamp(), 0.8)
    write("pad.wav", pad(), 0.5)
    write("click.wav", click(), 0.6)
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.wav"))))
