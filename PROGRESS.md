# Afterhours progress

## BLOCKED

1. **Archive RPC for Robinhood Chain mainnet (needed for the fork).** The public RPC
   (`rpc.mainnet.chain.robinhood.com`) serves state for only about the last 1,000 blocks
   (under 16 minutes; `cast code ... --block head-10000` fails with "historical state ... is not
   available"). Anvil cannot fork at the pinned `fork_block` (72388902, Friday 2026-09-25
   13:00 ET) without an archive node. Please create `.env` from `.env.example` and set
   `RH_MAINNET_RPC_URL` to an archive-capable endpoint (Robinhood's docs recommend Alchemy:
   one app for Robinhood Chain mainnet). Also set `RH_TESTNET_RPC_URL` and the Arbitrum URLs while
   you are there. Blocks: fork-block checks in M1, fork tests in M5, M6 and M7 on the fork.
   Unblocked meanwhile: discovery at head, the oracle study (logs only), M2 to M4, M5 unit tests.

2. **M11 live testnet deployments need keys you create and fund, and a hosting choice.**
   Everything else is ready: `./scripts/rehearse-testnet.sh rh-testnet` and `... arb-sepolia`
   deploy, seed and run a bot cycle on forks of both testnets at head (2026-09-27). Measured
   there: the deployer spent 0.0065 ETH (Robinhood testnet) and 0.0066 ETH (Arbitrum Sepolia),
   the allocator 0.0013 ETH per chain for the first allocation; curator and guardian nothing.
   Please:
   a. Run `cast wallet new` four times and put the private keys in `.env` as `DEPLOYER_PK`,
      `CURATOR_PK`, `ALLOCATOR_PK`, `GUARDIAN_PK` (testnet only; the same keys can serve both
      testnets). I never read `.env`.
   b. Fund from each chain's official faucet: deployer at least 0.02 testnet ETH and allocator
      at least 0.02 (the bot pays gas for every rebalance), on Robinhood Chain testnet and on
      Arbitrum Sepolia. Curator and guardian: 0.001 each for emergency actions.
   c. RPC URLs are optional: without `RH_TESTNET_RPC_URL` / `ARB_SEPOLIA_RPC_URL` the engine uses
      the public RPCs recorded in `config/afterhours.yaml`.
   d. Hosting (M11 asks for a hosted API and web app): choose where the API plus bot runs (an
      always-on Python service with a small persistent disk for `data/`) and where the web app
      runs (any Next.js host), then either log in to their CLIs here or tell me you will deploy
      and I will prepare the config for that host.
   Then tell me in chat that it is ready and I run `PROFILE=rh-testnet make deploy seed` and the same for
   `arb-sepolia`, write the addresses to the README and point the hosted app at them.

## Milestones

- [x] M0 Bootstrap (2026-09-26, `d185414`)
- [x] M1 Discovery (2026-09-26; fork-block checks wait on BLOCKED 1)
- [x] M2 Data and gap study (2026-09-26)
- [x] M3 Model (2026-09-26; fallback applied: ships the EWMA baseline)
- [x] M4 Policy and backtest (2026-09-26)
- [x] M5 Contracts (2026-09-26; pinned-block fork runs wait on BLOCKED 1)
- [x] M6 Bot and API (2026-09-26; accepted on the local profile, fork run waits on BLOCKED 1)
- [x] M7 Simulation harness (2026-09-26; local profile, fork run waits on BLOCKED 1)
- [x] M8 Frontend foundation (2026-09-26)
- [x] M9 Frontend pages (2026-09-26; local profile, fork run waits on BLOCKED 1)
- [x] M10 End-to-end hardening (2026-09-27; local profile)
- [ ] M11 Live deployments (rehearsed on forks of both testnets; BLOCKED 2)
- [x] M12 Submission assets (2026-09-27; items marked TEAM and the testnet links remain)

## Log

### 2026-09-26 Session start

- Kit found in `~/Desktop/afterhours-kit`, no git repo yet. Initialised git on `main` and committed the kit as-is (`44a6fb7`).
- Toolchain on this Mac (arm64, 16 GB RAM): no Homebrew, so installed without sudo into the home folder:
  - uv 0.12.19 (`~/.local/bin`), CPython 3.12.14 through `uv python install 3.12`;
  - Foundry 1.8.3 through foundryup (`~/.foundry/bin`);
  - pnpm 9.15.9 through `npm install -g` into the nvm Node 20.20.2 prefix.
- Not installed: Homebrew, `libomp` (LightGBM needs it; handled in M3), `gh`, Docker.
- Next: M0.

### 2026-09-26 M0 Bootstrap: done

What was done
- uv workspace (`pyproject.toml`, member `engine/`), Python 3.12, ruff, mypy strict on `engine/afterhours`, pytest.
- `engine/afterhours/config.py`: pydantic-settings model for every key in SPEC section 5, `extra="forbid"` everywhere. The loader validates YAML against `config/schema.json` (generated from the model by `make gen-schema`), then parses with pydantic. `AFTERHOURS_*` env vars override YAML (`__` for nesting). Fields ending in `_env` hold env var names, read with `cfg.env(name)`.
- `engine/afterhours/public_config.py` builds the secret-free document for `GET /v1/config/public`; `afterhours config {check,get,public,schema}` CLI.
- `web/`: Next.js 16.3.6, React 19.2, Tailwind 4, TypeScript strict, eslint (`--max-warnings 0`), prettier, vitest. `web/src/lib/config.ts` is the zod loader for the public config (from the API or a build-time file). Stub page with Bodoni Moda and Hanken Grotesk through `next/font`.
- `contracts/`: Foundry project, forge-std v1.16.2 as a root-level submodule.
- `.env.example` lists every variable with a comment and no secret values. The Makefile loads `.env.example` then `.env`, so ports have defaults before `.env` exists.
- `scripts/lint-hardcode.sh` (`make lint-hardcode`): greps tracked and untracked source for 40-hex addresses and http(s) URLs outside `config/`, `deployments/`, `docs/`, test folders and markdown. A line can opt out with `hardcode-ok` plus a reason (used for the JSON Schema spec id and the toolchain installer URLs in `make setup`). Verified it fails on a planted address.
- `.githooks/pre-commit` (hardcode check, ruff; config tests and `forge fmt` when those files are staged), enabled by `make setup`.
- Stack targets (`fork`, `deploy`, `seed`, `engine`, `api`, `up`, `demo`, `report`) exist and exit 2 naming the milestone that fills them in.

Evidence
- `make setup` exit 0.
- `make lint` exit 0: ruff, ruff format, mypy strict (5 files, no issues), eslint, `tsc --noEmit`, prettier, `forge fmt --check`, lint-hardcode clean.
- `make test` exit 0: pytest 9 passed (includes "schema file is up to date", env override, unknown key and wrong type rejected); vitest 6 passed; `scripts/config-roundtrip.sh` writes a temp YAML with a random `vault.symbol`, and both the Python CLI and the web zod loader print the new value.
- `make web` serves `/` with HTTP 200.

Acceptance
- `make setup`, `make lint`, `make test` pass on this Mac: pass.
- A config value changed in YAML is visible in both loaders: pass (`make test-config`).

Notes
- The web app reads config only through the public document, never the YAML. That keeps one YAML reader (Python) and one validator per language.
- Forge tests are skipped with a message until M5 adds the first `.t.sol`.

Next: M1 discovery.

### 2026-09-26 M1 Discovery: done (fork-block checks pending an archive RPC)

What was done
- `afterhours discover` (`engine/afterhours/discovery/`): fetches Robinhood's token page and assets API, Chainlink's feed directory, Morpho's SDK address book and API, and Uniswap's `deployments.json`; checks every address onchain; measures Uniswap sell depth with the official quoters; studies weekend oracle updates. Writes `deployments/fork.discovered.json` (every address with source URL and evidence) and `artifacts/discovery/oracle_study.json`.
- `scripts/verify-discovered.sh` (`make verify-discovered`): independent check with plain `cast` calls.
- `contracts/test/fork/StockTokenTransfer.t.sol`: deciding fact 2 as a fork test.
- Config filled with verified values: chain ids and explorers for all four networks, public RPCs, `fork_block` 72388902 (Friday 2026-09-25 13:00 New York time), `vault_kind: vault-v2`, per-profile `morpho_source`, timelock one day (source allows 0; reason in config), `stale_minutes` 1470 (feeds use a 24 h heartbeat). SPEC updated for the per-profile Morpho source.
- Full write-up: `docs/findings/m1-discovery.md`.

The three deciding facts
1. Weekend oracles: frozen. 8 weekends x 35 feeds: nothing after Friday 20:00 New York time except closing prints within 105 seconds, silent until Sunday 20:00. Feeds do update in the weeknight overnight session. On restart, feeds move 0.89% on average and up to 7.75% (USO).
2. Transfers: unrestricted. 10 of 10 fork tests pass for the 5 selected tokens (fresh accounts, arbitrary contract, Morpho collateral in and out). `collateral_mode: native`.
3. Vault: Vault V2 factory on Robinhood Chain (isVaultV2 true for 45 of 45 listed vaults). Neither testnet has Morpho: testnets self-deploy.

Evidence
- `uv run afterhours discover`: 0 failures; head block 73,040,830; selected NVDA, SPY, META, SGOV, USO (sell depth at 2%: $2.20M, $1.46M, $1.28M, $1.20M, $1.08M).
- `make verify-discovered`: 81 passed, 0 failed.
- `FORK_RPC_URL=<public> STOCK_SYMBOL=<s> forge test --match-path test/fork/StockTokenTransfer.t.sol`: 10 passed.
- Enabled LLTVs: 0, 38.5, 62.5, 77, 86, 91.5, 94.5, 96.5, 98%. Liquidation incentive formula verified in source and bytecode.

Other findings
- Public RPC keeps only minutes of state (BLOCKED 1). Two bugs found and fixed on the way: calls pinned to an old block silently returned nothing, and load-balanced nodes lag the head. RPC errors now raise; only reverts count as failed calls.
- Stock Token lending on Robinhood is early: 6,115 USDG borrowed across all Stock Token/USDG markets. No live rates to copy.

Acceptance
- `deployments/fork.discovered.json` with evidence for every address: pass (checks at `fork_block` are recorded as skipped until an archive RPC is set).
- `cast`-based verification script passes: pass (81/81).
- Decisions recorded: pass.

Files: `engine/afterhours/{chain,discovery}/`, `scripts/verify-discovered.sh`, `contracts/test/fork/`, `config/afterhours.yaml`, `deployments/fork.discovered.json`, `artifacts/discovery/`, `docs/findings/m1-discovery.md`.

Next: M2 gap study (dataset is built), then M3 results and M4.

### 2026-09-26 M2 Data and gap study: done

What was done
- Providers in config order with a Parquet cache and manifest (`data/cache/manifest.json`): prices from yfinance (Stooq and Alpha Vantage as fallbacks), split and dividend adjusted because Stock Tokens reinvest dividends; earnings with before-open or after-close timing.
- Universe: current S&P 500 constituents (survivorship bias noted in the artifact) plus every Stock Token with a feed: 523 tickers.
- Dataset: one row per ticker and closed period, target `g = open_next / close_prev - 1`, segments (earnings > holiday > weekend > overnight) and the SPEC 7.3 features plus an EWMA volatility column.
- Lookahead test: every price after a cutoff is rewritten at random; all features on rows up to the cutoff must be identical (`engine/tests/test_dataset.py::test_no_lookahead`).

Evidence
- `uv run afterhours data build`: 2,032,976 rows, 523 tickers, 2010-01-04 to 2026-09-25; prices 524/524 from yfinance; earnings 517 from yfinance (6 ETFs have none); timing known for all but 59 of ~44,000 events. Runtime about 20 minutes, mostly earnings requests (under the 20-minute threshold, so no Kaggle).
- `uv run afterhours gaps`: `artifacts/gaps/summary.json`, `gap_hist_{selected,universe}.png`, `gap_tail_{selected,universe}.png`.
- Headline (universe): earnings nights open down 5% or more 8.94% of the time and 10% or more 2.05%; 1% quantile -13.1%. Weekends: 10% or more down 0.14% vs 0.03% for overnights; 1% quantile -3.5% vs -2.8%.
- Selected tokens: worst gaps META -24.5% (earnings, 2022-10-26), META -24.3% (earnings, 2022-02-02), USO -21.9% (weekend, 2020-03-06).

Acceptance
- `artifacts/gaps/summary.json` and figures by segment for the selected tokens: pass.

Next: M3 (model runs are done; write up).

### 2026-09-26 M3 Model: done, fallback applied

What was done
- Baselines (SPEC 7.4): (a) global empirical quantile per segment, (b) per-ticker per-segment empirical quantile with a fallback below 30 rows, (c) EWMA volatility (lambda 0.94) normal quantile scaled by sqrt(closed hours / 24).
- LightGBM quantile regression for alpha 0.01 and 0.05, one global model.
- Mondrian conformal calibration by segment, applied the same way to the model and to every baseline.
- Rolling walk-forward: 6 train years, 1 calibration year, 1 test year; 10 folds, test years 2017 to 2026 (2026 partial). Everything reported is from test years only: 1,229,403 held-out rows.
- `afterhours model` writes `artifacts/model/report_card.json`, `calibration_<segment>.png` (for the shipped method) and `production.json` (latest train and calibration windows, corrections for every method, model version hash).

Variants tried (all kept for disclosure in `artifacts/model/variants/` and listed in the report card)
1. Raw target, additive conformal scores: model pinball 5.31e-4 vs EWMA 4.80e-4. Model wins on earnings, holidays and weekends, loses on overnights (77% of rows) and badly in 2020 (calibrated on calm 2019).
2. Volatility-standardised target, additive scores: model 6.41e-4, worse.
3. Volatility-standardised target, normalised conformal scores (Lei et al. 2018; the correction scales with the EWMA gap scale): model 5.46e-4 vs EWMA 4.58e-4. This is the current config.
Stopped here: more tuning against held-out years would be fitting to the test set.

Result (variant 3, alpha 0.01, pooled held-out)
- LightGBM: miss rate 1.83% overall (pass, within 1 point), 1.23% on earnings (pass, within 2 points); pinball beats baselines (a) and (b) but not (c). Acceptance: fail.
- Shipped: `ewma_normal` with Mondrian normalised calibration. Miss rate 1.30% overall, 1.08% earnings, 1.72% weekend, 1.13% overnight, 2.74% holiday (the weak spot: about 9 holiday closes per calibration year). At alpha 0.05: 5.35% overall, 5.27% earnings.
- Production calibration (train 2020 to 2025, calibrate 2026): corrections in gap-scale units for the shipped method: earnings +6.79 (much fatter tail than the normal quantile), weekend -1.36, overnight -0.82, holiday -1.44. Model version `2975043dcd63122f`.
- Feature importance (model, gain share): VIX 26%, VIX 5-day change 23%, market return 20%; per-ticker volatility much lower, which is why a per-ticker volatility scale wins.

Evidence: `uv run afterhours model` (about 3 minutes; each LightGBM fit about 4.5 s on 724k rows). Tests: `engine/tests/test_model.py` (folds, pinball, Mondrian CQR hits target per segment on synthetic heavy tails, baselines).

Acceptance
- `report_card.json` meets 7.4 or the fallback is applied and stated: pass (fallback applied; the report card's first sentence says so; README states it).

Next: M4 backtest and tuning.

### 2026-09-26 M4 Policy and backtest: done

What was done
- `engine/afterhours/policy/lp.py`: the SPEC 7.5 LP on HiGHS (allowed-tier rule with Morpho's verified incentive, borrowed floor, caps, per-stock limit from max share and pool depth, turnover penalty, minimum rebalance).
- `engine/afterhours/backtest/`: economics simulator (borrower LTVs uniform over 60% to 98% of LLTV, bad debt from Morpho's liquidation formula, loans rolling a set share per session), the four strategies, a 60-point tuning grid, rate-spread and loan-turnover sensitivities, and 12 replay scenarios picked from the data (3 largest gaps per segment). Only held-out forecasts are used (2017 to 2026).
- Three simulator problems found and fixed on the way, each covered by a test: static strategies were placing money less efficiently than the LP (now the same LP restricted to one tier); a market pulled to its borrowed floor wrongly re-lent repaid loans (now repaid loans are not replaced at 100% utilisation); reallocation counts included interest drift.
- New policy setting `lookahead_closed_periods` (default 1 = SPEC 7.5). The allocator can only move unborrowed USDG, so one close of notice cannot shrink open loans (tested). Acting on the worst bad case over the next N closed periods lets loans roll off before a scheduled risky night; future forecasts use only what is known at the decision close (today's volatility rescales each future period's calibrated quantile).

Tuned values (rule: highest Afterhours net yield among settings whose worst single event loses at most 0.1% of the vault; 18 of 60 settings qualified)
- `morpho.lltv_tiers`: weekday 91.5%, weekend 77% (both enabled on Robinhood's Morpho).
- `policy.safety_margin` 0.05, `policy.lookahead_closed_periods` 3.
- `backtest.vault_usdg` 2M, sized to measured Uniswap depth.

Results (`artifacts/backtest/results.json`, historical stock prices, simulated vault, 2,445 closed periods 2017-01-03 to 2026-09-25, NVDA SPY META SGOV USO)
| Strategy | Net yield | Bad debt | Worst event |
| --- | --- | --- | --- |
| Always weekday tier | 9.13% | $111,676 | 0.72% of vault (META earnings 2022-10-26) |
| Always weekend tier | 7.19% | $7,499 | 0.12% |
| Afterhours | 7.74% | $5,127 | 0.07% |
| Perfect foresight (same lookahead) | 9.25% | $68,268 | 0.46% |
- Afterhours beats always-weekend on both yield and bad debt in every sensitivity (rate spread 0.5x to 2x; loan turnover 5% to 100% per session). With faster loan turnover its bad debt falls further ($818 at 100%).
- Assumptions (rates by LLTV, 85% utilisation, 20% loan turnover, borrower LTV spread) are in config and in the artifact; Stock Token markets on Robinhood show almost no borrowing today, so there are no live rates to copy.

Acceptance
- Backtest artifacts for all four strategies: pass. Tuned values recorded with reasons: pass (config comments and this entry).

### 2026-09-26 M5 Contracts: done (pinned-block fork runs pending BLOCKED 1)

What was done
- `AfterhoursReasonRegistry` (SPEC interface; Ownable2Step; allocator-only `logReason`; seq starts at 1; rejects an empty hash), `SimOracle` (Morpho IOracle scaling 10^(36 + loan decimals - collateral decimals), Chainlink-style read), `SimStockToken` and `SimUSDG` (labelled "(sim)").
- `script/DeployAfterhours.s.sol`: reads a plan built from config and the discovered file by `afterhours deploy`; reuses or self-deploys Morpho (Morpho Blue, Adaptive Curve IRM, Vault V2 factory, Market V1 adapter factory), creates one oracle and two markets per token, creates the Vault V2 with owner, curator, allocator and sentinel (guardian) roles, adds the adapter, sets absolute and relative caps (35% per stock), performance fee, then one-day timelocks on cap raises, adapter changes, allocator changes and fees; deploys the registry; writes the deployment JSON. `afterhours deploy` adds tier metadata (b and cushion) to `deployments/<profile>.json`.
- New `local` profile (plain Anvil, self-deployed Morpho, simulated oracle and collateral) so M6 and M7 can run while the archive RPC is missing. `make local-chain`, `make fork`, `make deploy`.
- Compiler settings now match morpho-org/vault-v2 (via_ir, 100k runs); otherwise VaultV2Factory is over 24 KB. Our self-built Morpho is 15,582 bytes, the same as the one on Robinhood Chain.

Evidence
- `forge test --no-match-path "test/fork/*"`: 22 passed (registry incl. fuzz, sim contracts, and a local end-to-end deployment: allocator moves only unborrowed money, cannot raise caps or add adapters; curator raise waits 1 day; guardian cap cut blocks allocation; 35% stock cap enforced; deployment JSON written).
- `FORK_RPC_URL=<public> forge test --match-path test/fork/DeployFork.t.sol`: 2 passed at the chain head: the deploy script runs against Robinhood's real Morpho, Chainlink oracle factory, Vault V2 factory and USDG; oracle price equals the feed answer x 1e16; a real closing-bell move (deposit, allocate, borrow $60k, move the unborrowed $40k to the weekend tier, log a reason).
- `make deploy PROFILE=local`: 10 markets, vault, adapter, registry; `deployments/local.json`.

Acceptance
- `forge test` green including fork tests: pass at the chain head; the run pinned to `fork_block` needs the archive RPC (BLOCKED 1).
- `make deploy PROFILE=fork` writes `deployments/fork.json`: pending BLOCKED 1 (`make fork` needs the archive RPC). Verified the same script against the real contracts in the fork test above; `deployments/fork.plan.json` is written.

Next: M6 bot and API (developed on the local profile, then the fork once unblocked).

### 2026-09-26 M6 Bot and API: done on the local profile (fork run pending BLOCKED 1)

What was done
- Live risk (`engine/afterhours/risk/live.py`): the shipped calibrated baseline over the next closed periods from the exchange calendar, scheduled earnings and EWMA volatility up to "now"; drivers are an exact additive split (stock volatility, closed hours, segment calibration). On fork and local profiles "now" is the chain's clock, so the demo can move time.
- Allocator (`engine/afterhours/bot/allocator.py`): reads vault state onchain (allocation, lent-out amount from market liquidity, live supply APY via the IRM, caps, idle), solves the LP, executes deallocations then allocations with the allocator key (only unborrowed money moves), then builds one reason card per stock that moved, hashes it (RFC 8785 + keccak256, excluding `tx` and the stored hash), logs it with `logReason`, and stores it. A file lock keeps one cycle at a time across processes.
- Reason cards follow SPEC 7.7 with two stated differences: drivers are `{feature, contribution, detail}` plus `drivers_method` (the shipped forecaster is a baseline, so this is an exact split, not SHAP), and numbers are fixed-point strings so canonical JSON is stable across languages.
- Server-side verifier (`explain/verify.py`): recompute the hash, read `ReasonLogged` from the registry receipt, compare hash and subject.
- Scheduler (`bot/scheduler.py`): APScheduler tick; hourly, pre-close, post-open and pre-earnings marks on the profile's clock; shock, stale-oracle and pool-divergence triggers, each debounced.
- API (`engine/afterhours/api/app.py`, `make api`): every SPEC 8 endpoint plus `?replay=true` on the stream; simulation endpoints require the admin token and a fork or local chain. The bot and API share an append-only event log, so either can restart.
- Seeding (`afterhours sim seed`, `make seed`): lenders deposit, the bot allocates, borrowers borrow in every supplied market at LTVs drawn over 60% to 95% of the tier LLTV, via Anvil impersonation (Simulation).
- CLI: `afterhours bot once|run`, `afterhours sim seed`, `afterhours api`; `make engine` refreshes cached data then runs the scheduler.

Evidence
- `make test-integration` (engine/tests/integration/test_local_stack.py, 51 s): throwaway Anvil chain, `afterhours deploy`, `afterhours sim seed`, API server, then `POST /v1/sim/close-out`: every market's vault supply equals the plan target (within 0.01 USDG), every reason card verifies as "matched" against its registry event, and the stream delivered status, plan_changed, tx_sent, tx_confirmed, reason_logged and vault_updated.
- Manual run on the local chain: 5 lenders, 1,622,954 USDG (sim); 6 borrowers, 1,298,363 USDG (sim) borrowed; 3 reason cards, all matched onchain (seq 1 to 3).
- Unit tests: 47 Python tests pass (scheduler marks and triggers included); mypy strict clean.

Acceptance
- On the fork, a forced close-out moves funds exactly as planned, the registry event matches the recomputed hash, and SSE emits every event type: passed on the local profile (self-deployed Morpho, simulated oracle and collateral). The same code path runs on the fork once `make fork` has an archive RPC (BLOCKED 1); the fork deploy test already exercises the real contracts.

Next: M7 scripted scenarios and `make demo`.

### 2026-09-26 Session pause (usage limit): M7 nearly done, M8 started

Done since M6
- Scenarios (`engine/afterhours/sim/scenarios.py`, `afterhours sim scenario <name>`): closing_bell (steps bell by bell until a stock loses the weekday tier), earnings_shock (gaps a simulated oracle at the open, liquidates through Morpho, reports exposure and loss), oracle_drift (walks an oracle down; the shock trigger fires on the third 1.2% step).
- `make demo` / `make up` (`scripts/demo.sh`): local chain starting Tuesday 2026-08-18 13:00 New York (chosen by scanning 68 weeks; reason in config), deploy, seed, API, scheduler, web, closing-bell scenario. Verified unattended with DEMO_EXIT=1: Tuesday no moves; Wednesday's pre-close check moves SPY's unborrowed 113,607 USDG (sim) out of the 91.5% tier and places freed money in USO's 77% tier, each with an anchored reason card.
- Fixed on the way: live and assumed rates were mixed (the planner chased empty markets); reason cards now state the real cause (risk, rate or limit); risk-driven moves always execute, rate moves need 1% of the vault; dust moves under 1,000 USDG are skipped.
- `make report` = gaps, model, backtest.

In flight / next
- The backtest was rerunning to match the LP's new execution rule (risk moves always execute). When `artifacts/backtest/results.json` is regenerated, compare it with the M4 table above, update M4's numbers if they moved, and commit.
- Run `make test-integration` (engine/tests/integration/test_demo.py is new, not yet run) and then mark M7 done.
- M8: web dependencies are installed (gsap, motion, lenis, visx, wagmi 2, viem, RainbowKit 2, react-query, canonicalize, @noble/hashes, Playwright). Plan: one registered `--phase` CSS property mixes every day and night token with color-mix; art components in web/src/art; add a public RPC URL to /v1/config/public for the wallet. Check brass-button contrast (ink on brass is about 3.9:1, so labels need 19px bold to count as large text).

### 2026-09-26 M7 Simulation harness: done (local profile)

- Backtest regenerated after the execution-rule change: headline results unchanged (M4 table stands); sensitivity figures moved by at most 2 USDG.
- `POST /v1/sim/close-out` now jumps to the next pre-close check strictly after "now" (before, a second call on the same afternoon re-ran "now").
- Cycle results list `executed_markets` and the dust threshold, so "moved exactly as planned" is checkable: moved markets land on target to the cent; untouched ones differ by less than 1,000 USDG.
- `/v1/config/public` gains `chain.rpc_url`: the local node on fork and local profiles, else the chain's public RPC; never the .env RPC.

Evidence
- `uv run pytest -m integration engine/tests/integration/test_local_stack.py`: pass (chain starts at the demo week; close-out rings until the bot acts; plan matched, every card "matched" onchain, all six event types on the stream).
- `uv run pytest -m integration engine/tests/integration/test_demo.py`: pass in 52 s (`DEMO_EXIT=1 ./scripts/demo.sh`: de-risked SPY at Wednesday 2026-08-19 14:00 New York, reason anchored with a registry tx).

Acceptance
- `make demo` runs the closing-bell scenario end to end without manual steps: pass on the local profile (demo.profile). Switch `demo.profile` to fork once BLOCKED 1 is resolved.

Next: M8 frontend foundation.

### 2026-09-26 M8 Frontend foundation: done

What was done
- Tokens (`web/src/app/globals.css`): the seven DESIGN colour roles with day and night values. Two registered numbers drive the crossfade: `--phase` (art, 2.4 s, symmetric ease) and `--ui-phase` (text and surfaces, 300 ms at the sequence midpoint). Type scale, radii (frames stepped, panels 12, controls 10, badges round), no shadows, double rules, SVG grain, visible focus rings. Contrast: ink on limestone 12.3:1, moonlight on midnight 14.1:1; day brass carries only large text (buttons are 19px bold, since ink on brass is 3.8:1).
- Day/night engine (`web/src/lib/phase.tsx`): the phase follows `/v1/status` (the chain's clock on fork and local), the server renders the first paint in the right phase, each change bumps a bell counter; "Preview the close" flips locally without touching the real badge or countdown.
- Art in code (`web/src/art/`): ExchangeFacade (stepped setbacks, fluted columns, sunburst doors, pediment bell that swings on each session change, clock on New York time, windows lighting floor by floor straight from `--phase`, sun and moon, stars, two-layer skyline whose lit windows scale with activity, dusk glow and silhouettes mid-sequence), DecoFrame (double rule, stepped corners measured in pixels), SunburstDivider, TickerRibbon (live oracle prices, pauses on hover, static with reduced motion; a readable band under the frame on phones).
- Components: SiteHeader (nav, menu under 1024 px), SessionBadge, BellCountdown with SplitFlap digits (Motion), SimulationBanner, lazy WalletButton (RainbowKit and wagmi load on the first press, themed from tokens, chain from `/v1/config/public`), typed API client with zod schemas for every endpoint, React Query hooks, one SSE subscription that refreshes affected queries.
- API additions: `GET /v1/prices` (oracle prices for the ticker) and `chain.rpc_url` in the public config (browser-safe).
- QA tooling: `make screens` (Playwright, 1440/1024/390, day, night, mid-bell; flags horizontal overflow), `WEB_DEV_ORIGINS` for Next 16's dev-origin check.

Screenshot loop (three rounds; final set in `artifacts/screens/landing/`)
- Round 1: the page never hydrated on 127.0.0.1 (Next 16 blocks dev resources for non-localhost origins): made the allowed hosts configurable. Unlit night windows were pale grey: glass got its own day and night values. Headline sat far below the frame: trimmed the sky crop.
- Round 2: 1024 px used the 88 px headline and wrapped to five lines: 48/64/88 at base/lg/xl. The ticker started mostly empty: seamless two-copy loop. The in-art ticker was about 5 px on phones: a full-width band under the frame instead (and a cascade bug that kept the tiny one visible).
- Round 3: mid-bell, text and background crossed through the same grey (unreadable for about a second): split the UI phase from the art phase. The midpoint was flat grey: buildings now darken faster than the sky and the horizon glows at dusk. The preview from night half-mixed palettes and the badge claimed the exchange was open: snap to day, then ring; badges follow the real session. Night grain lifted midnight: grain reduced at night.
- Checks: no horizontal overflow at any width; reduced motion gives a 300 ms linear crossfade, a static ticker and no bell swing; focus rings visible.

Evidence
- Lighthouse on the production build (`artifacts/lighthouse/landing.json`): performance 94, accessibility 100, best practices 96. The one failed audit is a console error because the API's CORS list covers the dev port, not the test port.
- `pnpm lint` (eslint with the React Compiler rules, tsc strict), `pnpm test` (8 passed), prettier clean, `make lint-hardcode` clean.

Acceptance
- Screenshots at three widths in both modes reviewed and saved: pass (`artifacts/screens/landing/{day,night,bell}-{1440,1024,390}.png`).
- Lighthouse targets met on a stub landing: pass (94 and 100).

Next: M9 pages (Vault, Almanac, Ledger, Replay, Report card, the landing scroll story).

### 2026-09-26 M9 in progress: Ledger, Vault, verify in browser, deposit and withdraw

Done
- Verify on chain in the browser (`web/src/lib/verify.ts`): RFC 8785 (`canonicalize`) + keccak-256 (`@noble/hashes`), then the ReasonLogged event read with viem from the card's registry transaction. A vitest pins the browser hash to the hash the Python bot anchored for a real card.
- Telegram (reason card as a printed slip with driver bars) and VerifyBadge (matched or mismatched, both hashes, event number, block, transaction).
- Ledger page: telegram rail, stock filter, paging, empty state naming the next pre-close check (public config now carries the schedule).
- Vault page: position and deposit panel, session badge and countdown, AllocationBoard (brass bars sized by USDG, lent-out part hatched, idle reservoir with the reserve line, bars glide when money moves and the row flashes on tx_confirmed), latest three telegrams.
- Wallet: one lazily loaded set of wagmi and RainbowKit providers shared by the header and the vault (WalletGate).

Bugs found by the new end-to-end test and fixed
- The wallet modal listed no wallets (RainbowKit needs connectorsForWallets): now the browser wallet always, MetaMask, Rainbow and WalletConnect when NEXT_PUBLIC_WC_PROJECT_ID is set.
- Vault V2 pays withdrawals only from idle cash and its liquidity market (maxWithdraw always returns 0), and the bot kept almost nothing idle: new `policy.idle_reserve_share` 0.05 in the LP, and the bot now sets the liquidity market (SPEC 6.3 "where new deposits go") to the safest allowed weekend-tier market, logged as a `queue_reorder` reason.
- Deposits reverted with RelativeCapExceeded because the liquidity market's stock was already at its 35% cap: the bot now routes only to markets with at least `policy.liquidity_min_headroom_share` (5%) of room, else to idle cash.
- Share amounts used USDG's 6 decimals instead of the vault's 18; withdraw gas estimates were too tight (OutOfGas): the panel adds a 30% buffer to its own estimate.
- Sim-only faucet `POST /v1/sim/faucet` (local profile, simulated USDG, per-address cooldown).

Backtest regenerated with the 5% idle reserve (same tuned setting): Afterhours 7.47% net yield and $5,122 bad debt; always weekend 6.85% and $7,491; always weekday 8.84% and $108,748; perfect foresight 8.96% and $65,615. Afterhours still beats always-weekend on both in every sensitivity. These supersede the M4 table above.

Evidence
- `WEB_BASE_URL=... ANVIL_RPC_URL=... pnpm exec playwright test` (web/e2e/vault.spec.ts): pass in 14 s: faucet, deposit 1,000 USDG (sim), withdraw 400 through the UI with an in-page test wallet on the local chain.
- Ledger in the browser: "Matched onchain" for the SPY de-risk card (registry event #4, block 168).
- vitest 12 passed; eslint and tsc clean; Python tests, ruff and mypy clean.

Next: Almanac, Replay, Report card, landing scroll story; screenshot loop for every page.

### 2026-09-26 M9 Frontend pages: accepted

Done
- Report card (`/report-card`): the first sentence is the artifact's own fallback statement; acceptance table (the LightGBM model misses pinball vs the EWMA baseline), calibration plot per segment for the shipped forecaster, held-out miss rate and pinball for all four forecasters by segment, backtest table for the four strategies, sensitivity table, gap tail curves, methods with numbers read from the model config.
- Replay (`/replay`): scenario picker (list on wide screens, select on phones), one price timeline of the real path with night bands you can click or scrub, "Ordinary vault" and "Afterhours" stages with split-flap bad debt counters, and the reason Afterhours would have written at each close. Opens on the worst drop. Labelled "historical stock prices, simulated vault".
- Almanac (`/almanac`): ruled-paper spread of the next 14 days, closed periods as night bands, earnings bells, each stock's bad-case bar against the weekday and weekend limits (cushion minus margin), a list layout on phones; clicking a stock opens its RiskGauge, drivers and tier reasons.
- Landing scroll story: gap histogram from the M2 study, the two fixed settings from the backtest, the vault's board now, the latest telegram, the replay teaser, the report card numbers. GSAP ScrollTrigger is loaded only on wide screens without reduced motion; otherwise each step shows its visual inline.
- Engine: replay files carry per-period series for both vaults, tier cushions and allowed tiers; `/v1/report-card` serves gap histograms, tail curves and the model config.

Fixed along the way
- The demo integration test shared the running stack's chain, deployments and state because `demo.sh` sourced `.env.example` over the test's ports. Scripts now load env files without overriding what the caller set (`scripts/env.sh`), and the test uses its own deployments and state directories.
- Lighthouse found contrast failures (ticker text and RainbowKit's button at 16 to 17 px on day brass, tier labels on the surface colour) and layout shift on the almanac; fixed. Heavy modules (the verifier) no longer load on pages that only need driver bars.

Evidence
- Screenshots: `artifacts/screens/{landing,vault,almanac,ledger,replay,report-card}/{day,night}-{1440,1024,390}.png` and `landing/bell-*.png`; no horizontal overflow at any width.
- `make lighthouse` (production build, mobile): landing 91/100, vault 88/100, almanac 93/100, ledger 89/98, replay 92/100, report card 87/100 (performance/accessibility); best practices 100 on all.
- `make e2e`: deposit and withdraw pass on the local chain. Verify on chain: matched in the browser (M9 in-progress entry).
- `make test-integration`: 2 passed. vitest 25 passed (every committed replay artifact parses with the page schema). ruff, mypy, eslint, tsc, prettier, forge fmt, lint-hardcode clean.
- Deposit and withdraw on the fork wait on BLOCKED 1; accepted on the local profile, labelled Simulation.

### 2026-09-27 M10 End-to-end hardening: accepted

Done
- Playwright suite (`make e2e`, `scripts/e2e.sh`), desktop 1440 and mobile 390 projects, against the running stack:
  - `demo.spec.ts`: landing, a forced close-out through the admin endpoint until money moves, the new telegram in the ledger, Verify on chain shows "Matched onchain", the vault board.
  - `vault.spec.ts`: faucet, deposit 1,000 USDG and withdraw 400 through the UI with an in-page test wallet (fresh random address per run).
  - `pages.spec.ts`: all six pages render live data with nothing left loading, no alerts, no console errors, no horizontal scroll.
  - `states.spec.ts`: API unreachable on every page shows what happened and "Retrying in 10 seconds."; empty ledger names the next plan; empty replay list says so.
  - `motion.spec.ts`: with reduced motion the story is not pinned, the ticker is static, the close preview still works, the replay offers "Jump to the gap".
- `afterhours data fetch`: prices and earnings for the five vault stocks only; `make demo` calls it so a clean clone needs no full data build.

Bugs the suite found, fixed
- Every page crashed to the Next error screen when the API was down, if the wallet had been opened: RainbowKit's button rendered outside the wagmi providers. The button now waits for them.
- wagmi with `ssr: false` reconnects during render and updated RainbowKit's modal mid-render (React error on the vault page); now `ssr: true`, which reconnects in an effect.
- Error messages said "Retrying shortly" but failed queries never refetched. They now refetch every 10 seconds and say so.
- The replay page showed "Loading" forever with no scenarios.
- `make` read `.env.example` after the caller's environment, so ports passed by tests or a second checkout were ignored and a second demo reused the running chain. Environment now wins in both make and the scripts.

Clean-clone run (documented in README "Run it")
- `git clone` into a scratch folder, no `.env`: `make setup` exit 0 in 5 min 31 s; `DEMO_EXIT=1 ANVIL_PORT=18545 API_PORT=18000 WEB_PORT=13000 make demo` exit 0 in 1 min 12 s, closing-bell result `"derisked": true` with reasons anchored, on its own ports while another stack ran.

Evidence
- `make e2e`: 32 passed (1.4 min); vault and pages specs 39 of 39 over three repeats.
- `make test-integration`: 2 passed. vitest 25 passed. `make lint` clean.
- Fork and testnet runs wait on BLOCKED 1 and M11.

### 2026-09-27 M11 Live deployments: rehearsed, blocked on keys and hosting (BLOCKED 2)

Done
- `scripts/rehearse-testnet.sh <profile>`: Anvil fork of the testnet at head, four throwaway keys from `cast wallet new` held only in the process environment and funded with fork ETH, the real `afterhours deploy`, `sim seed` and `bot once`, deployments and state in a scratch folder, ETH spent per role.
- Testnet seeding: off Anvil, each simulated lender and borrower is a throwaway key (`cast wallet new`, stored mode 600 in the git-ignored state folder) signing real transactions; the deployer mints simulated tokens and sends each actor `sim.testnet_eth_per_actor` (0.0005 ETH). Mainnet profiles refuse seeding.

Evidence (2026-09-27)
- Robinhood Chain testnet (46630) fork at block 124796591: vault and 10 markets deployed, 5 lenders deposited 1,622,954 USDG (sim), 6 borrowers borrowed 1,233,445; deployer spent 0.006469 ETH, allocator 0.001253.
- Arbitrum Sepolia (421614) fork at block 313032307: same results; deployer 0.006645 ETH, allocator 0.001258.
- Forge's estimate for the deploy script alone: 30.3M gas, 0.0006 ETH on Robinhood testnet and 0.0019 ETH on Arbitrum Sepolia at the gas prices then.

Open: real testnet deploys and hosting (BLOCKED 2).

### 2026-09-27 M12 Submission assets

Done
- Submission requirements read from Colosseum's own FAQ and hackathon page, recorded with sources in `docs/findings/m12-submission.md`.
- `afterhours numbers` writes `artifacts/report/numbers.json`: 64 numbers with their text and source artifact. `make lint-numbers` (part of `make lint`) fails if the README or a video script quotes a percentage or thousands-separated number that is not in it.
- README rewritten: problem with measured numbers, how it works, results, architecture diagram, run guide, deployments, limitations, prior work.
- Video scripts with shot lists: `docs/video/demo.md` (2:45, under the 3:00 limit) and `docs/video/pitch.md` (2:30, inside 2:00 to 3:00). `make scenario NAME=closing_bell` rings the bell on camera.
- Brand: code-drawn mark (`web/src/app/icon.svg`, now the favicon), `artifacts/brand/logo-512.png` and `wordmark-1200x630.png` (`web/scripts/brand.ts`).
- Builder update drafts for every milestone in `updates/` (11 files).

Fixed along the way
- The landing page said every Stock Token feed stopped moving over the weekends. The oracle study says 32 of 35 feeds posted nothing between Friday 20:00 and Sunday 20:00 New York; AMD, SGOV and SNDK posted 5 updates in all, each within 105 seconds of Friday 20:00. The sentence is now generated from the study (served in `/v1/report-card`).

Submission checklist (every field from Colosseum's FAQ, `docs/findings/m12-submission.md`)
- [x] 1. Product name and brief description: "Afterhours: a lending vault for Robinhood Stock Tokens that lends at full speed while the stock market is open and calm, moves lender money to safer Morpho markets before the market closes into risk, and writes the reason for every move onchain." (README first paragraph.)
- [x] 2. Blockchains and tools: Robinhood Chain (primary) and Arbitrum; Morpho Blue and Morpho Vault V2; Chainlink price feeds; USDG; Robinhood Stock Tokens; Uniswap v3 and v4 quoters for sell depth; Foundry, Python (FastAPI, LightGBM, SciPy HiGHS), Next.js, wagmi and RainbowKit, Playwright.
- [ ] 3. Teammates, backgrounds and previous experience. TEAM: each teammate needs a Colosseum account; the team leader adds them in the submission.
- [ ] 4. Where the team is located. TEAM.
- [x] 5. Logo or graphic: `artifacts/brand/logo-512.png`, `artifacts/brand/wordmark-1200x630.png`.
- [ ] 6. GitHub repository link. TEAM: the repository has no remote yet. Create a GitHub repository (public encouraged; a private one needs access for Colosseum's reviewers) and push, or ask me to once it exists.
- [ ] 7. Presentation video, 2 to 3 minutes. Script and shot list ready (`docs/video/pitch.md`); TEAM fills in the market, quotes, team and ask lines, then records.
- [ ] 8. Demo video, 3 minutes or less. Script and shot list ready (`docs/video/demo.md`); TEAM records it with `make up`.
- [ ] 9. Go-to-market, demand validation, distribution. TEAM: KICKOFF.md asks for 3 calls with DeFi lenders or vault curators; their quotes and any numbers on demand go in the pitch and the form. We have no traction to claim.
- [x] Prior work disclosure: README "Prior work" (repository started 2026-09-26, after the hackathon opened on 2026-09-14; open-source protocols composed, not written).
- [ ] Testnet deployment addresses and links in README: BLOCKED 2.
- [ ] Builder updates: drafts in `updates/`. Colosseum's FAQ describes weekly updates as one-minute videos; TEAM can read the drafts as scripts (edit them in your own voice first).
- [ ] Pre-submission audit on 2026-10-10 (KICKOFF.md): clean-clone `make demo`, every number checked against `artifacts/`, every simulated element labelled, testnet links checked, honest limitations in the README.
- [ ] Submit by 2026-10-11 (target; hard deadline 2026-10-12 23:59 PDT). TEAM, as team leader in the Colosseum portal.

Evidence
- `make lint`: clean, including lint-numbers and lint-hardcode. `make test`: Python 49 passed, vitest 25, forge 22 passed (2 fork tests skipped without a fork URL). `make e2e`: 32 passed.

### 2026-09-27 Decision rule for option A (written before any run)

Context: read-only runs showed NVDA and META almost never qualify for the weekday tier (the flat
5-point margin leaves a 1.11% limit against a 6.1% cushion), and a fixed per-stock map (SPY and
SGOV weekday, the rest weekend, no forecast) beat Afterhours on bad debt, worst event and
interest. The team chose option A: retune against a fair fixed-map baseline.

Rule (set by the team, not to be changed after results are seen):
- Tune only on closed periods from 2017 through 2021. Evaluate once on 2022 through 2026.
- The dynamic strategy wins only if, on 2022 to 2026, it has less bad debt than the
  no-hindsight fixed map at equal or higher interest.
- If it does not win, ship option B (fixed per-stock tiers plus pulling unborrowed money before
  risky nights) and say so plainly in the README and the report card.
- Report all strategies on both the 5 vault stocks and the full Stock Token universe.
- README, pitch.md and demo.md change only after this rule has been applied.
- Time box: one working day for A. The LightGBM multiplier (item 5) waits until A is decided.
