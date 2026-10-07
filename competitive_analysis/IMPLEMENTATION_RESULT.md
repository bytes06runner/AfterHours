# Afterhours implementation result, 2026-10-07

Branch `claude/fervent-fermi-dz6ion`, starting from `213d7af` (clean tree, equal to origin; no
earlier session's changes were present). All work is in local commits, **not pushed**:

| Commit | What |
|---|---|
| `226f962` | Automation: dense schedule, recorded cycles (hold or act), `/v1/automation` |
| `334882e` | DEX reads: public-RPC fallback, explicit `dex_status`; market snapshot and `market_now.*` |
| `847573f` | Docs: testnet source verification, onchain roles and timelocks |
| `08a1c22` | Truth pass; bad case quoted with its measured held-out miss rate |
| `79d241a` | Curator view (`/v1/live/curator`, `/curators`); `harden-timelocks`; guardian funding |
| (final) | PROGRESS, builder update, this report |

## Completed

### P0-A Truth pass: DONE

Each claim was checked against artifacts, the chain or the GitHub Actions API, then corrected:

| Claim (where) | Truth | Now says |
|---|---|---|
| "the same code runs on Arbitrum" (README) | Nothing deployed on Arbitrum | Deploy scripts target Arbitrum Sepolia (rehearsed on a fork); nothing deployed |
| "bot runs before each US close" (README) | 32 scheduled runs, none inside a window (Actions API) | Schedule described as it is; links `/v1/automation`; last cycle manual 2026-09-27 |
| Telegram alerts "Live, messages before a risky close" (README) | No pre-close alert ever sent | Commands work; no pre-close alert sent yet |
| Deposit and withdraw on the site (README pages table) | Hosted testnet has no faucet for visitors | Local demo chain only |
| "Saturday 2026-10-04", "last Saturday" (README, pitch, demo, update draft) | 2026-10-04 was a Sunday | "Sunday 2026-10-04 at 10:34 UTC" |
| IONQ, RGTI "drifted 3.4% and 7.3%" (README, pitch, demo) | Pools with $50 and $73 of depth (`artifacts/regime/snapshot-2026-10-04T1034Z.json`) | -3.4% and +7.3% in thin pools, "not price discovery" |
| "real markets pay lenders 0.0016% today", "6,182 borrowed" (README, pitch, landing band, report card) | Measured today: 15.4% supply APY, 1,665,217 borrowed, 96.7% lent | New dated numbers; the old ones kept only with their block and date |
| "We wrote the test down before running; our first design failed it, so this simpler design ships" (pitch) | B was defined after A's held-out results, a second look at the same window | Says exactly that |
| META "lost 59% less" (pitch) | Depends on the assumed loan turnover | Tied to the assumption |
| "nobody can be liquidated" (pitch) | Liquidations can happen at a stale price | "no loan is liquidated on what the stock is really doing" |
| "A real session" (Agents page, docs, README) | A scripted MCP client, not an LLM conversation | "A captured session", said so |
| "ML-curated", "AI-curated" | Not found in README, pitch, demo or web copy (CLAUDE.md's internal description only) | Unchanged |
| Pre-rendered animation voiceover ("0.0016% today", "6,182") | Audio can't be regenerated here | Flagged in `pitch.md`: do not use those two clips |

`make lint-numbers` is clean: every number in README, pitch and demo is in `numbers.json`.

### P0-B Automation: DONE (code); first scheduled run pending a push

- Root cause, from the Actions API: `cron: "23 * * * 1-5"` produced 32 runs from 2026-09-28
  to 2026-10-07 at irregular times (05:35, 14:12, 20:36 UTC, ...). The first 21 failed on a bad
  action tag; the 11 that succeeded all started outside 18:00 to 20:00 UTC, so the bot step was
  skipped every time.
- `.github/workflows/pre-close.yml`: `7-59/10 18-20 * * 1-5` and `7-59/20 15-17 * * 1-5`
  (every regular and early close, daylight and standard time, at least 5 chances per window,
  tested); manual dispatch keeps working and gains `force_cycle`. `actionlint` passes.
- `engine/afterhours/bot/automation.py`: every run writes a heartbeat; every cycle writes a
  record with `cycle_id` (`pre_close:<close>` or `manual:<run>`), `trigger_source`, `run_ref`
  (`github-actions:<run id>`), `started_at`/`finished_at`, `inputs` (vault totals, each stock's
  forecast, limit and pull state, model version, plan SHA-256), `policy`, `decision` (`hold` or
  `act`), `reason`, `txs`, `reason_ids`, `status`, `error` (URLs redacted). Idempotent per
  close; a running record blocks a duplicate until it times out
  (`automation.running_timeout_minutes`); a failure fails the job and is retried by the next run.
  `bot once` records manual cycles too. Nothing is invented: a hold records no transaction.
- Evidence in this container: a real `bot once --dry-run` against the testnet vault read the
  vault and failed at the forecast (Yahoo is blocked here); it was recorded as `failed` with
  the error, not dropped.

### P0-C Current market data: DONE

`RH_MAINNET_RPC_URL= uv run afterhours market-size --snapshot` (public RPC, no key), block
**82,622,425**, 2026-10-07 16:43:38 UTC: 149 USDG markets, **1,721,781** supplied,
**1,665,217** borrowed, **96.7%** utilization, 99.97% of supply at 62.5% LLTV, borrow APY
15.9%, supply APY 15.4%. NVDA, SPCX, GOOGL and AAPL carry 99.7% of the debt; GOOGL and AAPL are
100% lent. The WAR ROOM's "~$1.66M" is confirmed, its "~98%" is 96.7% overall. Full write-up:
`competitive_analysis/current-market-measurement.md`; artifact
`artifacts/report/market_snapshot_82622425.json`; `numbers.json` gains `market_now.*`.

### P0-D DEX reads: DONE (code); production confirmation pending a deploy

Root cause traced (`competitive_analysis/dex-read-verification.md`): pools, ABIs, token order
and decimals are correct (NVDA 237.1486 USDG from its v3 pool; 35 of 35 locally). One
rate-limited or failed batch made `regimes()` set **all** 35 prices to None, which looked the
same as "no pool". Reproduced here (the public RPC rate-limited this container: 35 of 35 empty).
Fix: fall back to the public RPC at its own block and budget; per-token
`dex_status` (`ok`, `no_pool`, `no_price`, `unavailable`); `regimes.dex` says which RPC
answered and why one failed; last good depth kept with `depth_as_of`. UI shows "DEX
unavailable". 4 new tests.

### P0-E Contract verification: DONE (already, not by this session)

All 18 testnet contracts (vault, registry, Morpho, IRM, factories, adapter, simulated tokens and
oracles) are verified on the explorer, partial match (the best possible with
`bytecode_hash = "none"`), `verified_at` 2026-10-07 16:23 to 16:28 UTC, before this pass
started. No redeploy, no re-verification. Table and re-verify command:
`competitive_analysis/contract-verification.md`.

### P0-F Agent coverage: DONE

`get_weekend_risk`, the REST summary, the risk board, the position checker and the Agents page
no longer say "1 night in 100". They print the 1% target and the shipped forecaster's measured
held-out miss rate for that kind of closed period, read from `report_card.json`
(`held_out_coverage`): for a weekend, "falls went beyond it on 1.73% of weekend periods (about
1 in 58)", holiday 2.74%. New field `held_out_miss_rate` in the agent response model. The model
and its numbers are unchanged.

### P0-G Automation health: DONE

`GET /v1/automation`: `status` is one of `never_ran`, `waiting_for_first_close`, `running`,
`ok`, `missed`, `failed` (or `not_applicable` without a deployment), with `healthy`,
`heartbeat` and its age, `last_cycle`, `last_successful_cycle`, `expected_closes`,
`missed_closes`, `current_window_close`, `next_close`. `?strict=true` answers 503 when
unhealthy (for an uptime monitor). `/v1/health` carries a summary and stays `ok`, so Render
never restarts over a stale bot.

### P1-H Curator view: DONE

`GET /v1/live/curator` and `/curators` (`engine/afterhours/live/curator.py`): for each live
USDG Morpho market against a Stock Token, tonight's bad case against the cushion (the board's
forecast and `tier_spec`, no second model), the highest enabled LLTV that survives (and with
the vault's margin), utilization and exit liquidity, borrower count and largest share (Morpho
`Borrow` events plus `position()`, scanned in the background and kept in the shared store),
feed state and regime, and one call: Reduce cap, Do not increase, Watch, or "Survives the
modelled bad case" (never "safe"). Thresholds in config `curator` and `policy`.

On the measured snapshot with production's forecasts (overnight, 2026-10-07): no market
breaches; 6 markets holding 99.6% of the debt are Watch because lenders cannot exit; 43 survive.
Feed state and price quality are shown but do not change the call (the weekend freeze is
already in the weekend segment's calibrated bad case; flagging it made every market Watch).

### P1-I Role and timelock hardening: DONE (tooling); onchain change is a founder step

Read onchain: owner, curator, allocator, guardian are EOAs; the guardian has 0 ETH; the exit
gates, adapter registry, management fee, fee recipients, force-deallocate penalty and abdicate
have no timelock. `afterhours harden-timelocks --profile <testnet>` raises those to
`vault.timelock_seconds` (submit then execute, curator key, raises only, testnet only, asks
first). Rehearsed read-only against the testnet vault: 10 functions at 0 s, 20 transactions; I
declined at the prompt, nothing sent. `fund-allocator --role guardian` sends
`funding.guardian_eth`. No multisig exists on this testnet; access control is not redesigned.

## Blocked

| Item | Why | What unblocks it |
|---|---|---|
| A real scheduled cycle | The workflow change is local and scheduled workflows run only from the default branch | Push and merge (founder) |
| Live check of `/v1/live/curator` and the DEX fallback in production | Needs a Render deploy; the public RPC rate-limited this container on wide reads | Push, then the commands below |
| Forge tests, deploy-script change | Foundry's installer host is blocked by this environment's egress policy (403) | Founder machine: the patch below plus `make test-sol` |
| Testnet bot dry run end to end | Yahoo is blocked here (403), so no price cache | Runs in GitHub Actions and on Render as before |
| `make test-integration`, full `make e2e` | No Anvil here | Founder machine |

## Tests

| Command | Result |
|---|---|
| `make test-py` (engine and agents) | 161 passed, 2 integration deselected (2 min 35 s); 1 pre-existing warning (duplicate OpenAPI id for `/v1/health` HEAD) |
| `make lint-py` (ruff, ruff format, mypy strict) | clean, 68 files |
| `make lint-web` (eslint, next typegen, tsc, prettier) | clean |
| `make test-web` (vitest) | 26 passed |
| `make test-config` | python and web see the same value |
| `make lint-hardcode`, `make lint-numbers` | clean |
| `actionlint .github/workflows/pre-close.yml` | clean |
| Playwright `e2e/curators.spec.ts` (local API and dev server, preinstalled Chromium) | 4 passed (desktop and mobile) |
| Screenshot loop, `/curators`, 1440, 1024, 390, day and night | 49 rows, no overflow, no page errors; nav fixed after review |

New tests: `test_automation.py` (14: schedule, manual dispatch, hold, act, already pulled,
duplicate, running-then-timeout, failure and retry, heartbeat, never ran vs held, shared store,
workflow coverage, API), `test_dex_reads.py` (4), `test_curator.py` (9), agent coverage (2),
hardening (2), `time.test.ts` coverage text, `curators.spec.ts` (2 per viewport).

## Deployment verification

Nothing was deployed or pushed. No transaction was signed. After the push and Render deploy:

```bash
API=https://afterhours-api.onrender.com
curl -s $API/v1/automation | jq '{status, heartbeat, last_cycle, missed_closes}'
curl -s $API/v1/live/regimes | jq '.dex, ([.tokens[].dex_status] | group_by(.) | map({(.[0]): length}) | add)'
curl -s $API/v1/live/curator | jq '{block, totals, summary, top: .markets[0] | {symbol, lltv, bad_case_drop, cushion, recommendation}}'
curl -s "$API/v1/agent/weekend-risk/NVDA" | jq -r .summary
```

## Remaining limitations

- The pullback has still never run on a public chain; the next scheduled cycles will most
  likely record holds (no 2026 trigger under policy B, PROGRESS 2026-09-27).
- The curator view's forecasts come from the shipped baseline; weekend 1.73% and holiday 2.74%
  held-out miss rates, stated on the page.
- Borrower concentration starts empty after a cold start until the background `Borrow` scan
  finishes (shown as "still scanning").
- Testnet tokens, oracles and USDG remain simulated; roles remain single EOAs; no audit.
- GitHub may still drop scheduled runs; health now says so (`missed`), it cannot prevent it.

## Founder actions required

1. Review and push the commits, then merge to the default branch (the schedule only runs there):
   ```bash
   git log --oneline 213d7af..claude/fervent-fermi-dz6ion
   git push -u origin claude/fervent-fermi-dz6ion
   ```
2. After Render redeploys, run the four `curl` checks above. Optionally add an UptimeRobot
   monitor on `/v1/automation?strict=true` (alerts on a missed or failed close).
3. After the next weekday window (18:00 to 20:00 UTC), confirm `last_successful_cycle` has
   `trigger_source: "schedule"` before saying the bot runs on schedule anywhere (pitch section 3
   says this too). A manual check outside the window: Actions, "Pre-close jobs", Run workflow,
   `force_cycle: true` (recorded as manual, never as a scheduled close).
4. Testnet hardening (curator key from `.env`, about 20 testnet transactions; prints the plan
   and asks first):
   ```bash
   uv run afterhours harden-timelocks --profile rh-testnet
   uv run afterhours fund-allocator --profile rh-testnet --role guardian
   ```
5. Future deploys: add the same selectors to `guarded` in `contracts/script/DeployAfterhours.s.sol`
   (`_curate`), then `make test-sol` (not done here: no Foundry). The list is
   `vault.harden_timelock_functions` in config.
6. Rotate the Alchemy and Upstash credentials (exposed in earlier sessions).
7. Record the pitch with section 7 (re-measured market) and the curator view; get one curator
   quote before saying anyone wants it.

## What should be done next

1. Push, deploy, and watch the first in-window run land as a recorded hold.
2. Show the curator view to the curators funding the 62.5% markets (WAR ROOM traction list);
   ask whether "which LLTV survives tonight, and how much can my lenders withdraw" would change
   their caps.
3. Re-read the market weekly (`market-size --snapshot`) and keep the dated series; reconcile
   each weekend's forecast with what happened (the report card's promise).
4. Only then: real testnet stock tokens (P1-2) or the Solana read-only decision (P1-4).
