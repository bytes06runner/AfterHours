# Regime monitor DEX reads: why `dex_price` was null, and the fix

Investigated 2026-10-07 between 16:40 and 16:55 UTC.

## Symptom

`GET /v1/live/board` on production (block 82,588,071, 2026-10-07 15:45 UTC, a regular session)
returned `dex_price: null`, `divergence: null`, `depth_usd: null` for 35 of 35 Stock Tokens.
Every quality score said `"used": ["staleness"]`. The WAR ROOM saw the same at 15:32 UTC.

## Trace of one token (NVDA)

Script: the engine's own `Mainnet.dex_prices`, run locally against the chain's public RPC
(`RH_MAINNET_RPC_URL` empty, so no API key).

- Pools from `deployments/fork.discovered.json`: v3 `0xd4EB…14a3` (USDG, fee 500) and v4 pool id
  `0x3bb3…4bf1` (USDG, fee 3000, tick spacing 60, no hooks), both with NVDA
  (`0xd060…9EEC`) against USDG (`0x5fc5…d168`).
- Block 82,623,430: `dex_prices(["NVDA"])` returned **237.1486 USDG**. The NVDA feed read 237.19
  at the same time. Pool address, ABI (`slot0`, v4 `StateView.getSlot0`), token order and
  decimals are correct.
- All 35 tokens, same call: **35 of 35 prices in 3.7 s**. The full board then gave 35 of 35
  `dex_price`, `divergence` and `depth_usd`, and every score used all three marks.

So the read is correct when the node answers.

## Root cause

1. `call_many` (`engine/afterhours/chain/rpc.py`) raises `RpcError` or `TimeoutError` for any
   error other than a revert, including a rate limit that outlasts the time budget. That is
   intended: a node problem must not look like a failed check.
2. `Mainnet.regimes()` caught that exception, logged one warning and set **every** token's DEX
   price to `None`. A single rate-limited batch erased all 35 prices, and the output could not
   be told apart from "this token has no pool".
3. The trigger is RPC rate limiting during a board refresh. One refresh sends about 70 feed
   calls, then about 70 pool calls, then many quoter calls for depth, in batches of 50.
   Reproduced here: after three back-to-back board reads from this container, the public RPC
   rate-limited us and the next refresh logged
   `TimeoutError: the node is rate limiting; out of time budget`, giving 35 of 35 empty.
   After a pause, prices came back (35/35) and the heavier depth quoting hit the limit again.
   On production the primary RPC is the Alchemy endpoint set on Render. The 2026-09-27 PROGRESS
   entry already records that Alchemy's free tier "answers some batched calls with a per-call
   429 (compute units per second)". That explains why production stayed at 0 of 35 while a
   fresh local run gets 35 of 35. We could not read Render's logs from here, so the exact
   production exception is inferred, not observed.

## Fix (minimal, in `engine/afterhours/live/mainnet.py` and `live/regime.py`)

- **Fallback.** If the DEX read fails on the primary RPC, it is retried once on the chain's
  public RPC (already used for log scans), at that node's own block and with its own time
  budget. Depth quotes use whichever client answered.
- **Explicit state, never silent.** Each row's `regime` now carries `dex_status`: `ok`,
  `no_pool` (no USDG pool at discovery), `no_price` (the pool answered without a usable price)
  or `unavailable` (the read failed). The board's `regimes.dex` block says which RPC answered
  (`source`), at which `block`, and the redacted error per RPC (`errors`, `depth_error`).
- **Depth.** If a depth re-quote fails, the last good quote is kept and labelled with its time
  (`regimes.dex.depth_as_of`). With no earlier quote, depth stays empty and says why.
- Unchanged: the score weights, thresholds, pools, the forecast, and what a failed read means
  (no mark, renormalised over the marks that exist, as `docs/REGIME.md` describes).

## Tests

`engine/tests/test_dex_reads.py` (no RPC; fakes for both clients):

- primary fails with a rate-limit `RpcError` and public answers: source `public`, 35 rows `ok`,
  divergence used, error redacted (no URL path in it);
- both fail: 35 rows `unavailable`, both errors recorded, score uses staleness only;
- a pool with no price: that row is `no_price`, the others `ok`;
- depth re-quote fails: the last good depth is kept with `depth_as_of`; none before it means none.

`uv run pytest engine/tests/test_dex_reads.py engine/tests/test_regime.py engine/tests/test_live_budget.py`: all pass.

Live check after the fix (public RPC, block 82,626,101, 16:49:55 UTC): `dex.source = primary`,
35 of 35 `dex_status = ok`, quality uses two marks, and depth re-quote rate-limited (reported in
`depth_error`). Largest divergences at that moment: IONQ +3.97%, CLSK +1.91%, RKLB +1.17%,
RGTI −3.30% (pool price against feed, during a regular session).

## What production needs

Deploy this commit to Render. If Alchemy's limit still blocks the primary, the public fallback
takes over, and `GET /v1/live/regimes` shows it in `regimes.dex.source`. If both are limited,
the rows say `unavailable`, and the landing copy now says the monitor falls back to feed
staleness when DEX reads are unavailable.

## Copy that depended on this

The snapshot `artifacts/regime/snapshot-2026-10-04T1034Z.json` (Sunday 2026-10-04 10:34 UTC,
block 79,868,354, feeds frozen) has IONQ at −3.41% with $50 of depth within 2%, and RGTI at
+7.30% with $73. These are moves in very thin pools, not price discovery. The truth pass labels
them that way and gives the date (not "last Saturday").
