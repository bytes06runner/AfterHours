# Price regime monitor

Robinhood announced weekend trading of a curated list of US stocks and ETFs through Bruce ATS,
pending regulatory review (docs/findings/robinhood-2026-09-29.md). If Stock Token feeds start
following a weekend venue, the lending risk changes from "no price" to "thin price". The
monitor says, for every Stock Token on Robinhood Chain mainnet and at every board refresh, which
regime its price is in and how much that price deserves to be trusted. It is read-only.

Code: `engine/afterhours/live/regime.py` (logic), `engine/afterhours/live/mainnet.py` (reads).
API: `GET /v1/live/regimes`, and a `regime` block on every row of `GET /v1/live/board`.
Settings: `regime` in `config/afterhours.yaml`.

## Regimes

| Regime | When |
| --- | --- |
| Regular session | The exchange (XNYS calendar, early closes and holidays included) is in its regular session. |
| Extended hours | Outside the session but in the hours the feeds keep posting: after hours, overnight, pre-market. These are the oracle study's own segments, matching Robinhood's 24 Hour Market (Sunday 20:00 to Friday 20:00 New York). |
| Weekend price | The exchange and those hours are both shut (the weekend window, holidays), and the feed has posted since the shut stretch began, more than `regime.window_grace_seconds` (300 s) after it. A weekend price source exists, and it may be thin. |
| Frozen | Shut, and the feed has posted nothing since the stretch began (a straggler inside the grace period does not count; M1 saw them up to 105 s after the window opened). |

The shut stretch's start is found on the same calendar, to the minute: Friday 20:00 New York on
a normal weekend, Wednesday 20:00 before Thanksgiving, and so on.

## Price quality score

A weighted mean, 0 to 100, of three marks in [0, 1]. Weights `regime.weights`: staleness 0.4,
divergence 0.4, depth 0.2. A mark that cannot be measured is left out and the weights of the
others are renormalised; the API lists the marks used.

- **Staleness.** `t` is the feed's typical minutes between updates in this regime (regular or
  extended), measured from the weekend oracle study files (`artifacts/regime/cadence.json`,
  `make regime-cadence`: updates counted per segment, divided into the hours of that segment
  the study read). With feed age `a` in minutes, zero point `z = max(stale_multiple * t,
  stale_floor_minutes)` (6 and 30):
  `staleness = 1` if `a <= t`; `1 - (a - t) / (z - t)` floored at 0 otherwise; `0` when frozen.
  Feeds post on a 0.5% move or a 24 h heartbeat, so a calm feed is old without being wrong; the
  multiple and floor keep it from being punished at once.
- **Divergence.** `d = DEX mid / feed - 1`, the mid of the deepest USDG pool that answers.
  `divergence = 1 - |d| / schedule.triggers.divergence_pct` (2%), floored at 0. While a feed is
  frozen this is the drift the market has made since the feed stopped.
- **Depth.** `D` is the USD of the token sellable within `vault.max_slippage` (2%) across the
  `regime.pools_per_token` (2) deepest USDG pools, quoted with Uniswap's quoters at
  `regime.depth_probes_usd` and interpolated as in M1 discovery; re-quoted at most every 30
  minutes. `depth = log10(D / 10,000) / log10(1,000,000 / 10,000)`, clamped to [0, 1].

Grades: good at 80 and above, fair at 50 and above, poor below (`regime.grades`).

USDG is taken as 1 USD for pool prices and depth, as in M1 discovery.

## Onchain reads, verified

Checked on Robinhood Chain mainnet on 2026-10-04 with `cast` before use:

- v3 pool `slot0()(uint160,int24,uint16,uint16,uint16,uint8,bool)` on the NVDA/USDG pool
  `0xd4EB21209C4D6093f80B5b84f5C45cc093EA14a3` (token0 USDG, 6 decimals; token1 NVDA, 18): the
  sqrtPriceX96 gives 234.8 USDG per NVDA against the feed's 234.997.
- v4 `StateView.getSlot0(bytes32)(uint160,int24,uint24,uint24)` at
  `0xF3334192D15450CdD385c8B70e03f9A6bD9E673b` (from Uniswap's deployments list, recorded in M1)
  for pool id `0x3bb34a44...4bf1` (NVDA/USDG, fee 3000): sqrtPriceX96 consistent with the v3 pool.
- Quoters as in M1 (`uniswap_v3_quoter_v2`, `uniswap_v4_quoter` in
  `deployments/fork.discovered.json`).

## The bad-case forecast is not adjusted

The brief allows a documented, labelled regime adjustment to the live forecast. We do not make
one: every weekend read so far shows frozen feeds (M1 and `artifacts/discovery/oracle_readings`),
so there is no weekend-venue price history to calibrate an adjustment against, and an
uncalibrated number would break the rule that every number comes from a measurement. The
evaluated strategy, its settings and backtests are unchanged. When a feed is first seen in the
weekend price regime, the board says so, and the forecast stays labelled as the shipped model's.

## Snapshots

`make regime-snapshot` writes `artifacts/regime/snapshot-<time>.json` with every token's regime,
score, divergence and depth. The first, on Saturday 2026-10-04 (block in the file): all 35
feeds frozen since Friday 20:00 New York; every token had a DEX price; median absolute
divergence 0.36%; IONQ and RGTI beyond the 2% divergence trigger.
