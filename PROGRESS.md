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

## Milestones

- [x] M0 Bootstrap (2026-09-26, `d185414`)
- [x] M1 Discovery (2026-09-26; fork-block checks wait on BLOCKED 1)
- [x] M2 Data and gap study (2026-09-26)
- [x] M3 Model (2026-09-26; fallback applied: ships the EWMA baseline)
- [x] M4 Policy and backtest (2026-09-26)
- [x] M5 Contracts (2026-09-26; pinned-block fork runs wait on BLOCKED 1)
- [ ] M6 Bot and API
- [ ] M7 Simulation harness
- [ ] M8 Frontend foundation
- [ ] M9 Frontend pages
- [ ] M10 End-to-end hardening
- [ ] M11 Live deployments
- [ ] M12 Submission assets

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
