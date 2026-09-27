# Afterhours pitch: the animated video

A 2 minute 25 second animated pitch, built with [Remotion](https://www.remotion.dev) (React code
rendered to video; free for individuals, see its LICENSE). The six scenes follow the timings in
[`../pitch.md`](../pitch.md), and every number on screen is read from
`artifacts/report/numbers.json`, the same file the README and pitch are checked against. Scenes
that show real data say so; illustrations and backtests carry their labels ("Illustration",
"Historical stock prices, simulated vault").

| Time | Scene | What happens |
| --- | --- | --- |
| 0:00 to 0:20 | Hook | The bell, the exchange at night, all 35 real feeds freezing, a weekend gap |
| 0:20 to 0:50 | Product | USDG into the vault, the three tiers, the pre-close forecast, a pullback, a reason onchain |
| 0:50 to 1:20 | Claim | Afterhours above the line of fixed mixes, the test written first, modelled rates |
| 1:20 to 1:40 | One night | META, 2022-10-26: the gap and the two losses |
| 1:40 to 2:05 | Market | Morpho markets with Stock Token collateral today |
| 2:05 to 2:25 | Close | The name, the live links, your team's words |

## Make your final video

From this folder (needs Node 20 and Python 3):

```bash
npm install
```

1. **Your words for the last scene.** Open `src/team.json` and fill `who` (who you are) and `ask`
   (what's next and what you are asking for). Empty fields are simply not shown.
2. **Record your voiceover** reading `../pitch.md`, following the timings. To practise, render the
   version with the script as subtitles and read along:

   ```bash
   npm run render:script
   ```

3. **Put the recording in** `public/voiceover.mp3` (or `.wav` or `.m4a`), starting at 0:00. The
   night pad automatically gets quieter under your voice.
4. **Render the final video:**

   ```bash
   npm run render
   ```

   The file is `out/afterhours-pitch.mp4` (1920 x 1080, 30 fps).

To tweak anything while watching it play, run `npm run studio` and open the link it prints.

## Sound

`scripts/make_sfx.py` synthesises every sound (the bell, whoosh, tick, impact, stamp and the
night pad) from sine waves and noise, so there is nothing to license. `npm run render` regenerates
them first.
