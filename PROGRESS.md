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
   a. Run `make testnet-keys` in your own terminal: it writes `DEPLOYER_PK`, `CURATOR_PK`,
      `ALLOCATOR_PK`, `GUARDIAN_PK` into `.env` and prints only their addresses and the faucet
      link (testnet only; the same keys can serve both testnets). I never read `.env`.
   b. Fund from each chain's official faucet: deployer at least 0.02 testnet ETH and allocator
      at least 0.02 (the bot pays gas for every rebalance), on Robinhood Chain testnet and on
      Arbitrum Sepolia. Curator and guardian: 0.001 each for emergency actions.
   c. RPC URLs are optional: without `RH_TESTNET_RPC_URL` / `ARB_SEPOLIA_RPC_URL` the engine uses
      the public RPCs recorded in `config/afterhours.yaml`.
   d. Hosting: zero-budget setup prepared (Vercel Hobby, Render free, GitHub Actions, Upstash,
      UptimeRobot, GoatCounter); follow `docs/HOSTING.md`. Creating the accounts and pasting
      secrets into the dashboards are yours.
   Then tell me in chat that it is ready and I run `PROFILE=rh-testnet make deploy seed` and the same for
   `arb-sepolia`, write the addresses to the README and point the hosted app at them.

3. **Resolved 2026-09-27: WalletConnect project ID set in `.env` (git-ignored).** Was: Browser-extension wallets work
   without it (Brave Wallet, Rabby, Phantom, Coinbase Wallet, MetaMask and any wallet that
   announces itself through EIP-6963). Phone wallets and the WalletConnect QR code need a free
   project ID from Reown (the WalletConnect cloud dashboard). Please create one and set
   `NEXT_PUBLIC_WC_PROJECT_ID` in `.env` (and in the web host's environment when it is hosted);
   MetaMask mobile, Rainbow, OKX and the QR option then appear under "More wallets".

4. **Telegram alert bot needs a bot token.** The bot is built and tested with fakes; it has not
   talked to Telegram yet. Please:
   a. In Telegram, message @BotFather, send `/newbot`, pick a name and a username ending in `bot`.
   b. Put the token it gives you in `.env` as `TELEGRAM_BOT_TOKEN=...` (git-ignored; I never
      read `.env`). Optionally send BotFather `/setcommands` with: watch, unwatch, list, stop, help.
   c. Hosted (free setup): set `TELEGRAM_WEBHOOK_SECRET` too, and after the API is on Render run
      `make telegram-webhook URL=<Render URL>` (docs/HOSTING.md steps 2 and 7). Pre-close alerts
      are sent by the GitHub Actions workflow. Locally, `make alerts` still long-polls.
   Then message your bot `/watch NVDA` and tell me in chat; I will check a real round trip.

5. **GoatCounter analytics needs your site's count endpoint** (replaced Plausible, which is
   paid). Sign up at goatcounter.com, pick a code, and set `NEXT_PUBLIC_GOATCOUNTER_URL` to
   `https://<code>.goatcounter.com/count` in Vercel (docs/HOSTING.md step 10). The script loads
   only in production builds and only from `web.analytics.script_src`; nothing is shown to
   visitors.

## FEATURE FREEZE (2026-09-27)

From now on only bug fixes, hosting configuration and documentation changes. No new features,
pages, endpoints, strategies, settings or backtests. Analysis stays frozen as before.

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

### 2026-09-27 Option A: step 1 findings and the pre-registered grid (before the sweep)

Step 1 (read-only, reproduces results.json exactly: 5,122 USDG):
- 84% of Afterhours' bad debt is META in the weekend tier (4,278 of 5,122), almost all from two
  earnings nights: 2022-10-26 (2,228) and 2022-02-02 (2,017). The fixed map lost 1,028 and 931
  on the same nights because it held about half as much META (time-weighted 260,747 vs 555,681
  USDG). Afterhours had flagged both nights and pulled the unborrowed part; the lent part stayed.
- The LP does shift money into NVDA and META when SPY is blocked from the weekday tier (mean
  supply NVDA 618k vs 556k, META 575k vs 534k, SPY 628k vs 726k). The backtest assumes one APY
  per tier for every stock, so once SPY leaves the weekday tier the LP is indifferent between
  stocks and per-stock exposure comes from tie-breaks and the turnover penalty, not risk.

Step 3: Morpho Blue on Robinhood Chain has 86% LLTV enabled (EnableLltv events, rechecked with
isLltvEnabled, M1). Liquidation incentive factor 1.043841 (Morpho's formula with the cursor 0.3
and the 1.15 cap verified in the deployed bytecode), cushion 10.23%. Added as a middle tier.

Grid and selection, fixed now (config `backtest.option_a`):
- Periods: tune on closed periods from 2017 to 2021; evaluate once on 2022 to 2026, each with a
  fresh 2,000,000 USDG vault. Universes: the 5 vault stocks and all 35 Stock Token underlyings.
- Dynamic Afterhours: tier sets {weekday+weekend, weekday+middle+weekend} x margin fraction
  {0, 0.1, 0.2, 0.3, 0.4, 0.5} (bad case must fit cushion x (1 - f)) x lookahead {1, 3, 5, 10}.
- No-hindsight fixed map: same tier sets x the same margin fractions; each January each stock
  gets the highest tier whose limit covers its worst 1% closed-period gap over the previous 365
  days (at least 60 observations, else the weekend tier); at least the weekend tier always.
- Selection on the tuning period, same rule as M4 for both families: highest interest among
  settings whose worst single event loses at most 0.10% of the vault; if none qualifies, the
  smallest worst event.
- Static blends 0% to 100% weekday in 5% steps, and the two pure tiers, reported on both periods.
- Decision (from the rule above): the chosen dynamic setting wins only if on 2022 to 2026 it has
  less bad debt than the chosen fixed map and equal or higher interest.

### 2026-09-27 Item 4: holiday miscoverage (2.74% against a 1% target): not a bug

- The per-segment (Mondrian) correction is applied to the shipped EWMA baseline in the
  walk-forward evaluation (`model/walkforward.py`, every forecaster including the baselines) and
  in the live forecast (`risk/live.py` applies `production.json` corrections for the period's
  segment; the holiday correction is -1.44 volatility units). Evaluation and live agree.
- The misses cluster on a few market-wide shocks: 93 held-out holiday dates, 1,280 misses, 68.4%
  of them on 5 dates (2021-11-24, the Friday after Thanksgiving; 2018-12-04, before the
  national day of mourning; 2018-12-31; 2025-01-08; 2020-09-04). Without those 5 dates the
  holiday miss rate is 0.92%. The median per-date miss rate is 0.40%; 32% of dates have none.
- Why the calibration misses them: each fold calibrates on one year, which holds only 8 to 11
  holiday dates, and about 500 stocks gap together on each. The effective sample is a handful of
  independent events, so the 1% correction is set by whichever few holidays that year had.
  Conformal guarantees assume exchangeable rows; rows on the same date are not.
- Possible remedies (not applied; they change the forecast used by option A mid-experiment):
  calibrate holidays on a longer window, or pool holidays with weekends (similar closed hours).

### 2026-09-27 Item 6: size of the Stock Token lending market on Morpho (mainnet)

- `afterhours market-size` at Robinhood Chain block 73,382,409 (2026-09-26 20:50 UTC):
  149 Morpho Blue markets use a Stock Token as collateral (285 markets in all; 147 of the 149
  were in Morpho's API at M1, the other 2 are 38.5% LLTV markets for SPY and NVDA). USDG-loan
  markets: 804,926 USDG supplied, 6,115 USDG borrowed. Largest by supply: SPCX 280,057, AAPL
  238,985, GOOGL 158,819, NVDA 106,623. Stored totals at the block, without interest accrued
  since each market's last update.
- Sources: CreateMarket events and `market(id)` layout from morpho-blue `IMorpho.sol` and
  `EventsLib.sol` (URLs in config); Morpho Blue, USDG and the 35 Stock Tokens from M1 discovery.
  Written to `artifacts/discovery/market_size.json` and `numbers.json` (`market.*`).

### 2026-09-27 Option A result: the dynamic strategy does not win; option B applies

`afterhours option-a` (324 runs, `artifacts/backtest/option_a.json`), grid and rule as
pre-registered in commit 813979f. Historical stock prices, simulated vault; each period starts
with a fresh 2,000,000 USDG vault. Evaluation 2022-01-03 to 2026-09-24 (1,186 closed periods):

| Strategy (chosen on 2017-2021) | 5 vault stocks: yield, bad debt, worst event | 35 Stock Tokens: yield, bad debt, worst event |
| --- | --- | --- |
| Always weekday | 9.34%, 12,521, 0.247% | 9.34%, 12,646, 0.244% |
| Always weekend | 6.88%, 595, 0.026% | 6.88%, 581, 0.026% |
| Static blend nearest the dynamic yield | 75% weekday: 8.72%, 9,145, 0.182% | 90% weekday: 9.09%, 11,461, 0.217% |
| No-hindsight fixed map (3 tiers, f 0.4 / 0.3) | 9.13%, 8,482, 0.199% | 9.28%, 13,380, 0.244% |
| Dynamic Afterhours (2 tiers, f 0.5, lookahead 10 / 5) | 8.67%, 748, 0.020% | 9.04%, 1,339, 0.025% |

Interest on evaluation: dynamic 963,015 vs fixed map 1,030,359 (vault stocks); 1,010,964 vs
1,054,466 (35 Stock Tokens). The dynamic strategy has less bad debt but less interest in both
universes, so under the rule it does not win. Option B applies.

Facts for the record, not grounds to change the rule:
- No fixed-map setting met the 0.10% worst-event cap on the tuning period (smallest worst
  event 0.543% and 0.538%), so the rule's fallback picked the fixed map with the smallest
  worst event. On evaluation it lost 0.199% and 0.244% of the vault in one event; the dynamic
  strategy's worst was 0.020% and 0.025%.
- With the margin as a share of the cushion, the dynamic strategy puts NVDA and META in the
  weekday tier far more often: 70% of money-time in the weekday tier on evaluation (vault stocks).
- Checked for artefacts: in the 35-stock universe 11 to 13 stocks each hold over 1% of the money;
  SPY and SGOV hold about 55% in every strategy because measured depth caps the others.

### 2026-09-27 Option B: definition and pre-registered grid (before any B run)

This is the second evaluation on the 2022 to 2026 held-out window (the first was option A,
commit e7a4e62). B was defined after seeing A's held-out results.

Definition (confirmed by the team):
- Tier placement: the no-hindsight fixed map over all three enabled tiers (91.5%, 86%, 77%
  LLTV). Each January each stock gets the highest tier whose cushion x (1 - map fraction)
  covers its worst 1% closed-period gap over the previous 365 days (at least 60 observations,
  else the weekend tier); never below the weekend tier.
- Pullback: on a night when the forecast bad case (the worst of the next `lookahead` closed
  periods) exceeds every tier's cushion x (1 - pullback fraction), that stock's unborrowed money
  goes idle. Otherwise the stock stays in its mapped tier. No per-night moves between tiers.
- Same LP, caps, idle reserve and simulator as option A.

Grid (config `backtest.option_b`): map fraction {0, 0.1, 0.2, 0.3, 0.4, 0.5} x pullback fraction
{0, 0.1, 0.2, 0.3, 0.4, 0.5} x lookahead {1, 3, 5, 10}; both universes (5 vault stocks, 35 Stock
Tokens).

Selection on 2017 to 2021 (the M4 rule): highest net lender yield among settings whose worst
single event loses at most 0.10% of the vault; if none qualifies, the smallest worst event.
Evaluate the chosen setting once on 2022 to 2026 with a fresh vault.

Correction on option A: A's pre-registration said "highest interest", not the M4 rule's
"highest net lender yield". Whether that changed A's choice is checked below after B runs.

### 2026-09-27 Option B result (second evaluation on 2022 to 2026)

`afterhours option-b` (576 runs, `artifacts/backtest/option_b.json`), definition and grid
pre-registered in commit 8f31b8e. Historical stock prices, simulated vault, fresh 2,000,000 USDG
vault per period.

Chosen on 2017 to 2021: 5 vault stocks map fraction 0.4, pullback fraction 0.4, lookahead 5;
35 Stock Tokens 0.3, 0.2, 10. No B setting met the 0.10% worst-event cap in tuning (0 of 144 in
each universe; the smallest worst event was 0.541% and 0.537%), so the fallback (smallest worst
event) chose them.

Evaluation, 2022-01-03 to 2026-09-24:

| Strategy | 5 vault stocks: yield, bad debt, worst event | 35 Stock Tokens: yield, bad debt, worst event |
| --- | --- | --- |
| B (fixed map + pullback) | 9.12%, 5,849, 0.107% | 9.37%, 4,444, 0.083% |
| Static blend nearest B's yield | 90% weekday: 9.09%, 11,132, 0.220% | 100% weekday: 9.34%, 12,646, 0.244% |
| No-hindsight fixed map (option A's choice) | 9.13%, 8,482, 0.199% | 9.28%, 13,380, 0.244% |
| Dynamic Afterhours (documented alternative) | 8.67%, 748, 0.020% | 9.04%, 1,339, 0.025% |
| Always weekday | 9.34%, 12,521, 0.247% | 9.34%, 12,646, 0.244% |
| Always weekend | 6.88%, 595, 0.026% | 6.88%, 581, 0.026% |

B's money-time on evaluation (vault stocks): weekday 73%, middle 19%, weekend 2%, idle 5%.
On the 5 vault stocks B's worst event (0.107%) is above the 0.10% cap.

Option A selection check: selecting A by net lender yield (the M4 rule) instead of interest picks
the same settings in both families and universes, so A's verdict is unchanged.

Ships: B, per the rule. Next: three tiers in the deploy, the bot on B's policy, then the report
card, landing chart, README, pitch.md and demo.md.

### 2026-09-27 Option B ships: bot, UI and documents

Done
- Deploy: three markets per stock (91.5%, 86%, 77% LLTV); the Solidity script takes an ordered
  tier list. `forge test` green; the mainnet fork deploy test passes at the chain head with three
  tiers on Robinhood's real Morpho, Chainlink and USDG.
- Bot and API: `policy/option_b.py` is the one implementation of B, used by the backtest and the
  bot (the refactored backtest reproduces option_b.json exactly: 5,849 USDG bad debt, 1,026,091
  interest). Config `policy`: map fraction 0.4, pullback fraction 0.4, lookahead 5 (B's choice
  for the vault stocks). `/v1/risk` reports each stock's rating, mapped tier and pullback state.
- A bug caught by that reproduction check before it shipped: the tier-map floor used the
  smallest cushion instead of the lowest-LLTV tier's (the widest).
- Demo week moved to 2025-04-22 (config `demo`): META, in the 91.5% tier by its 2025 rating, is
  pulled before its 2025-04-30 earnings. A 2026 week would show no move: scanning 2026, no stock
  that holds vault money is ever pulled under B at these settings.
- Replays rerun under B. META 2022-10-26: B had pulled META's unborrowed money five nights
  before; it lost 9,953 USDG against 24,300 for always-weekday (the old dynamic design lost 2,228).
- UI: allocation board with three tiers and each stock's map and pullback state; Almanac bars
  against the pullback limit with each stock's mapped tier; RiskGauge and Replay on B; report
  card decision section (verdict verbatim, frontier chart, tables for both universes, the facts
  below as statements); landing story led by B against the nearest fixed mix.
- Documents: README, pitch.md and demo.md rewritten for B; every number passes `make lint-numbers`.
  Stated as facts, as asked: the verdict verbatim; the fixed map broke the 0.10% cap in tuning
  (0.543%) and out of sample (0.199%); B against the nearest blend and against the fixed map;
  the dynamic strategy's results as a documented alternative; tier yields are assumed.
- Pitch market line uses the measured mainnet figures (149 markets, 804,926 USDG supplied,
  6,115 borrowed at block 73,382,409) and calls the market early.
- Item 5 (LightGBM multiplier) dropped, as decided.

Evidence
- `make e2e`: 32 passed. `make test-integration`: 2 passed. `make test`: Python, vitest and
  forge green. `make lint` clean, including lint-numbers.

### 2026-09-27 After the freeze: measurements, pitch cut, frontend, secret scan

Analysis frozen: no strategy, setting or backtest changed.

Measurements
- `afterhours b-activity` (`artifacts/backtest/option_b_activity.json`): replays B's evaluated run
  (reproduces its bad debt exactly) and counts nights the pullback fired for a stock holding
  unborrowed vault money. 5 vault stocks, 2022 to 2026-09-24: 228 nights (83, 35, 40, 40, 30 by
  year), 284 stock-nights, 10,241,622 USDG moved in all (money returns and is pulled again);
  META 134 and NVDA 138 stock-nights, USO 12. 35 Stock Tokens: 883 nights, 10,478,972 USDG.
  In numbers.json (`b5.pulls.*`, `b35.pulls.*`) and on the report card.
- Live Morpho rates: the public RPC no longer serves the pinned block 73,382,409 (state kept for
  about the last 1,000 blocks), so size and rates were re-read together at block 73,650,323
  (2026-09-27 04:22 UTC): 150 Stock Token markets, 804,926 USDG supplied, 6,182 borrowed (0.77%
  utilization), borrowing in 31 of 148 USDG markets; supply APY 0.0016% supply-weighted, borrow
  APY 0.20% borrow-weighted. Rates from each market's IRM `borrowRateView` at the block; supply
  APY = borrow APY x utilization x (1 - fee), from Morpho Blue `_accrueInterest`. README, pitch
  and report card now say backtest yields use modelled rates (7.0% to 9.5%) and give this figure.

Pitch
- `docs/video/pitch.md` cut to one claim in relative terms (B vs the nearest blend: 47% less bad
  debt, 51% smaller worst night; vs the fixed map: 31% and 46%, same yield), one replay (META
  2022, 59% less loss), one sentence on the pre-registered test, and the market line. 266 spoken
  words (about 1 minute 50 seconds), under 2:30 with the TEAM lines. Methods stay on the report card.

Frontend
- Welcome sequence (first visit per session, landing): bronze deco doors, bell medallion, a
  loading bar tied to real readiness (fonts, /v1/status, /v1/report-card), the bell rings and the
  doors swing open; Skip button and Escape; never with reduced motion; at most about 4 seconds.
- Full-width hero: on wide screens the exchange is drawn with the sky and skyline continued into
  wings on both sides, so the band fills the width without cropping the building; scroll parallax.
- Day and night life, all driven by --phase: drifting clouds by day; sweeping searchlights,
  twinkling stars, flickering windows and glowing street lamps at night.
- Header day and night switch on every page (a preview; the session badge stays real).
- Data animations on scroll: histogram bars grow, the blend line draws and points arrive in
  order with a pulse on B, comparison numbers flip in on split-flap digits.
- Full-width brass band of measured facts; skyline footer on every page.
- Layout shift fixed: the Simulation banner is now rendered by the server, main reserves height.

Evidence
- `make e2e`: 36 passed (new: the welcome opens by itself, once per session, and can be skipped).
- `make lighthouse`: landing 91, vault 86, almanac 95, ledger 87, replay 92, report card 89
  (performance); accessibility 98 to 100; best practices 100.
- `make lint` (including lint-numbers) and `make test` clean.

Secret scan (gitleaks 8.30.1, official release, checksum verified)
- Full history: 653 findings, all rule `generic-api-key`, all on JSON keys containing "token"
  whose values are 39 public Ethereum contract addresses (Stock Tokens and USDG on Robinhood
  Chain from discovery, and simulated USDG on the local chain). No private keys, `.env` files or
  key files are tracked.

### 2026-09-27 Wallet connection for real users

Reported: in Brave, choosing "Browser Wallet" left the modal spinning with no wallet window.
- Chains carry their official names and gas currency in config (docs.robinhood.com/chain/connecting:
  "Robinhood Chain", "Robinhood Chain Testnet", ETH; docs.arbitrum.io chain info: Arbitrum One,
  Arbitrum Sepolia), served in `/v1/config/public`, so a wallet asked to add the network gets the
  right name, currency, public RPC and explorer. No chain literal remains in the web app.
- Wallet list: Brave Wallet (shown in Brave), Rabby, Phantom, Coinbase Wallet and the generic
  browser wallet always; MetaMask, Rainbow, OKX and WalletConnect when a project ID is set
  (BLOCKED 3); other installed wallets appear through EIP-6963 discovery.
- Help under the wallet list (approve from the browser toolbar; in Brave the wallet icon), and
  if a wallet has not answered after 15 seconds an alert says where to approve.
- Testnet and mainnet: "Switch to <chain name>" and a link to the chain's faucet from config.
- Evidence: `e2e/wallet-stuck.spec.ts` (a wallet that never answers gets the hint) passes; the
  full suite passes.

### 2026-09-27 WalletConnect enabled; QR crash fixed

- The team supplied a WalletConnect (Reown) project ID; it is in `.env` as
  `NEXT_PUBLIC_WC_PROJECT_ID` (git-ignored, never committed). The modal now also lists MetaMask,
  Rainbow, OKX Wallet and WalletConnect.
- With QR wallets on, the page crashed ("RangeError: invalid border=0"). Cause: RainbowKit 2.2.11
  (the latest) draws QR codes with `cuer@0.0.3`, which accepts any `qr` 0.x and passes border 0;
  `qr@0.7.0` (and 0.6.0) reject a zero border, `qr@0.5.5` accepts it. Fixed with a pnpm override
  (`cuer>qr: 0.5.5`) in the root `package.json`.
- Verified: the Rainbow option shows a WalletConnect pairing QR with no page errors (which also
  confirms the relay accepts the project ID). New test in `e2e/wallet-stuck.spec.ts`; `make e2e`
  38 passed.
- Hosting note: the web host needs the same `NEXT_PUBLIC_WC_PROJECT_ID`, and if the Reown project
  has a domain allowlist, the hosted domain must be on it.

### 2026-09-27 Live, read-only tools for real users (mainnet)

Analysis stays frozen: no strategy, setting or backtest changed. The vault stays labelled
Simulation; the new pages say "Live: Robinhood Chain mainnet, read-only, block N".
- Risk board (`/live`, `GET /v1/live/board`): every Stock Token with a verified feed (35 today,
  from `discovered/`), its price, last update, whether it is frozen now (M1 window, in config
  under `live.frozen_window`) and tonight's forecast bad case, plus which USDG Morpho markets'
  cushions it reaches. Cached `live.board_cache_seconds`.
- Position checker (`/positions`, `GET /v1/live/positions/{address}`): any address or the
  connected wallet; per Morpho position borrowed, collateral, LTV, liquidation price, the fall to
  get there, and whether tonight's bad case reaches it. Markets come from CreateMarket events
  (registry in `data/state/live-markets.json`, rescanned every `live.market_refresh_minutes`).
  "Try a live borrower" offers addresses from Borrow events with an open loan (kept in
  `data/state/live-borrowers.json`, scanned incrementally and warmed when the API starts; first
  scan about 90 s, then milliseconds).
- Checked by hand against `cast`: 0x4987...C7CB holds 1,300 NVDA against 99,000.81 USDG in the
  62.5% market, LTV 33.7%, liquidation at 121.85 USDG.
- Telegram alerts (`afterhours alerts run`, `make alerts`): /watch a stock or an address,
  /unwatch, /list, /stop. Inside the pre-close window (`schedule.pre_close_minutes`) each
  subscription is checked once per close; it alerts only when tonight's bad case reaches a
  market cushion (stock) or a position's fall to liquidation (address). Token from
  `alerts.token_env`, never logged. Waits on BLOCKED 4 for a real round trip.
- All 35 Stock Tokens' prices are fetched (`afterhours data fetch --stock-tokens`, called by
  `demo.sh`, `make alerts` and the bot before each check), so every row has a forecast.
- Session and forecast times show New York time and the visitor's own time zone.
- Plausible: `next-plausible` in the root layout, production only, script host from config,
  site URL from `NEXT_PUBLIC_PLAUSIBLE_SRC` (BLOCKED 5). No UI.
- "About 1 night in N" now comes from the forecast's alpha instead of a literal.
- Evidence: `tests/test_alerts.py` (commands, limits, the pre-close window, once per close, quiet
  nights, restart); `e2e/live.spec.ts` (board rows match the API, filters, unreachable chain,
  invalid address, empty wallet, live borrower card with tonight's line). `make test-py` 60
  passed, `make e2e` 48 passed, lint, hardcode and numbers checks clean.

### 2026-09-27 Reconciled: checker shows 99,000.81 USDG debt, numbers.json says 6,182 borrowed

Both are correct, at different blocks. Checked onchain with `cast`:
- Market 0x8b16...9c3e: `idToMarketParams` gives loan token 0x5fc5...d168 (`symbol()` "USDG",
  "Global Dollar", 6 decimals), collateral NVDA, LLTV 62.5%. Total borrow 99,912.81 USDG; the
  address holds 98.8e15 of 99.7e15 borrow shares, so 99,000.8 USDG. The label was right.
- `numbers.json` (`market.usdg_borrowed`) is read at block 73,650,323 (04:22 UTC). Borrow events
  show 0x4987...C7CB borrowing exactly 99,000 / 100,000 / 101,000 USDG in the NVDA, SPCX and AAPL
  62.5% markets at block 73,670,925 (04:57 UTC), 35 minutes later. The same address borrowed and
  repaid about 300,000 on 2026-09-10 and about 186,000 on 2026-09-14.
- At block 73,832,105: 148 USDG markets, 804,927.22 supplied, 306,892.81 borrowed. The only
  other loan token is WETH (2 markets, 2.24 WETH supplied, 0 borrowed; `by_loan_token` in
  `artifacts/discovery/market_size.json` already lists it). No other stablecoin markets, so
  numbers.json is unchanged.
- The README and report card give the block with the figure. The pitch script (line 42 of
  `docs/video/pitch.md`) says "6,182 borrowed" with no date: flagged to the team, not changed.
- Bug fixed: the checker assumed USDG for the unit. Positions now carry `loan_token` and
  `loan_symbol` (the token's own `symbol()`, read onchain); a WETH loan would have read "units of
  the loan token" and a liquidation price with no unit. `e2e/live.spec.ts` checks the card shows
  the onchain symbol. `make e2e` 48 passed, `make test-py` 60 passed, lints clean.

### 2026-09-27 Hosting config and guide (feature freeze: hosting and docs only)

- `docs/HOSTING.md`: Render for the engine (API, bot, alerts in one service with one disk) and
  Vercel for `web/`, every environment variable per service, testnet faucets and RPCs, and the
  order to do it in. Platform facts checked in Render's and Vercel's docs on 2026-09-27.
- `render.yaml` (Blueprint): Python runtime, build `uv sync --frozen --no-dev`, start
  `./scripts/serve.sh`, health `/v1/health`, plan `1c-2g` (measured: API about 240 MB, bot about
  150 MB), disk at `/var/data`. State and cache paths move onto the disk through
  `AFTERHOURS_PATHS__STATE_DIR` and `AFTERHOURS_DATA__CACHE_DIR` (config overrides).
- `scripts/serve.sh`: binds `0.0.0.0:$PORT`, refreshes prices, starts the bot and alerts only
  when their key and deployment exist, restarts them if they exit. Tested locally with
  `PORT=8123`: listened on `*:8123`, `/v1/health` 200, state written to the override path.
- Least privilege: the bot now asks only for `ALLOCATOR_PK` (`role_keys(..., roles)`), so the
  deployer, curator and guardian keys never go to the server.
- `make fund-allocator PROFILE=...`: the deployer sends `funding.allocator_eth` (0.02) to the
  allocator; testnet profiles only, chain id checked, keeps `funding.keep_deployer_eth`, asks
  first, keys never on a command line. Tested on an Anvil fork of Robinhood Chain Testnet with
  throwaway keys: refused at 0.01 ETH, sent 0.02 at 1 ETH, refused `rh-mainnet` and `local`.
- On `rh-testnet` and `arb-sepolia` without a deployment, `/v1/health` is 200, the live board
  works and `/v1/vault` answers 404 "No deployment for this profile yet".
- Web: a production build with no API URL prerenders static pages; with
  `NEXT_PUBLIC_API_BASE_URL` set, every page renders per request. The guide says to set it
  before the first Vercel build.
- `engine/tests/test_hosting.py`: disk paths, required secrets, no deployer key on Render, bot
  key scope. `make test-py` 63 passed, `make lint` clean.

### 2026-09-27 Zero-budget hosting (feature freeze: hosting, bug fixes and docs only)

Checked every free tier in the provider's docs (sources in `docs/HOSTING.md`). One assumption
was wrong: Hugging Face Docker Spaces now need a paid plan (PRO) to create, so the API uses the
named fallback, Render free. Vercel Hobby is free for non-commercial personal use only.

- Web: Vercel Hobby, unchanged apart from analytics.
- API: Render free (`render.free.yaml`, 512 MB, sleeps after 15 minutes idle). Measured from an
  empty cache on the `rh-testnet` profile: prices for all 35 Stock Tokens, the board and the
  borrower scan ready in 21 s, peak 366 MB (macOS `time -l`) plus about 17 MB for `uv`.
  UptimeRobot pings `/v1/health` every 5 minutes to keep it awake.
- Telegram: webhook mode. `POST /v1/telegram/webhook` checks `X-Telegram-Bot-Api-Secret-Token`
  (constant-time) against `TELEGRAM_WEBHOOK_SECRET`; 404 when not configured, 403 on a bad
  secret, 200 otherwise so Telegram does not retry. `make telegram-webhook URL=...` registers it.
- Scheduled work: `.github/workflows/pre-close.yml`, hourly at minute 23 on weekdays; the engine
  decides (`afterhours pre-close`). Then `bot due` (one pre-close cycle per close, if deployed)
  and `alerts check` (once per subscription per close). `ALLOCATOR_PK` reaches only the bot step,
  the Telegram token only the alerts step; no deployer, curator or guardian key anywhere.
- Shared state: Upstash Redis over REST (`afterhours/kv.py`, no new dependency), used when
  `UPSTASH_REDIS_REST_URL` and `_TOKEN` are set. Bot history (`state.py` `KVStore`: events and
  reasons as lists, documents as keys, a lock with expiry) and Telegram subscriptions (one hash
  field per chat, pre-close bookkeeping in its own key, so the API and the job never overwrite
  each other). Reads cached 30 s and event checks every 30 s to stay inside 500K commands/month.
  Chose Upstash over Neon: HTTPS with a token (no driver on a 512 MB host, no connections from
  short jobs), key-value data, and Neon's free compute sleeps after 5 minutes.
- Analytics: GoatCounter replaces Plausible. Script from `web.analytics.script_src`, endpoint
  from `NEXT_PUBLIC_GOATCOUNTER_URL` on `endpoint_domain`, production only, SPA route changes
  counted. Verified in a production build with GoatCounter blocked: one script tag,
  `no_onload` set first, nothing sent.
- Bugs found and fixed while measuring:
  - On a testnet profile the live price fetch found no Stock Tokens (it read the testnet's
    discovered file, which does not exist): 0 symbols before, 35 after (`live.discovery_profile`).
    Test in `test_hosting.py`.
  - Concurrent requests to `/v1/live/examples` each started a full borrower scan (the public RPC
    answered 429 and memory reached 495 MB). Now one scan at a time; others get the cache at
    once. The board is computed once for concurrent callers too.
  - Prices are warmed inside the API process instead of a second Python process.
- Tests: `tests/test_shared_state.py` (fake Upstash: history round trip, cached reads, the lock,
  bad token, API and job not overwriting each other, webhook secret and replies, workflow and
  Blueprint secret audits). `make test-py` 75 passed, web 25, contracts 22, `make e2e` 48,
  `make lint` clean.
- Paid path kept: `render.yaml` with a disk.
- After pushing (the workflow is live on GitHub): `afterhours pre-close` crashed when its two-day
  range held no session (a Sunday, or a Monday holiday such as Labor Day). `sessions()` now
  returns an empty frame for an empty exchange schedule; tests for Sunday and 2026-09-07. And
  `alerts check` skips with a message when the Telegram token is not set yet, so scheduled runs
  stay green until the secrets are added. Checked locally with no secrets: `pre-close`, `bot due`
  and `alerts check` all exit 0.


### 2026-09-27 `make testnet-keys`

- `afterhours testnet-keys` (`make testnet-keys`): four keys from `cast wallet new` written into
  `.env` (empty `ROLE=` lines filled in place, others appended, atomic replace, mode 600). Prints
  roles and addresses only, then the faucet URL of `funding.faucet_profile` (rh-testnet) and the
  deployer address. Refuses, naming roles but no values, if any role already has a key.
- Not run on the real `.env`. Checked with real `cast` against a temp file (deleted after): no
  key-shaped string in the output, 4 roles filled, mode 600. `tests/test_testnet_keys.py`: in-place
  fill, new file, never overwrite (plain, `export`, quoted and spaced forms), CLI output has no key.

### 2026-09-27 Robinhood Chain Testnet vault deployed

- Budget re-estimated at live gas before deploying: an rh-testnet fork run, priced with
  `ArbGasInfo.getPricesInWei` (0.01 gwei L2 gas plus L1 data per byte). The faucet's 0.01 ETH
  covers it. Config only: `funding.allocator_eth` 0.02 to 0.002, `funding.keep_deployer_eth`
  0.005 to 0.001, `sim.testnet_eth_per_actor` 0.0005 to 0.00005, new `funding.curator_eth`
  0.0005.
- Bug found and fixed first: the curator signs 114 curation transactions during `make deploy`,
  but nothing gave it gas (the M11 rehearsal gave every role 100 fork ETH, so it never showed).
  `deploy` now has the deployer top the curator up to `funding.curator_eth`, only what it
  lacks, before the deploy script runs on a real chain. `rehearse-testnet.sh` starts the curator
  at 0 ETH, and gives fork actors more gas money because Anvil suggests a 1 gwei priority fee
  where the testnet suggests 0. Unit test for the top-up.
- Deployed at block `deployed_at_block` in `deployments/rh-testnet.json`: vault
  0xD4791630C02FF7462536bAEae7BcE13c5917E6d3, registry 0x2416C56ea86895cf2dE81eBe0Da1f742bDb30ee0,
  15 markets, simulated USDG, collateral and oracles. Checked onchain: vault curator, owner,
  guardian as sentinel and the registry's allocator are the four addresses from `.env`.
- Real spend: deployer about 0.00034 ETH for the deploy (estimate 0.00036), curator 0.000078
  (estimate 0.00008), allocator 0.0000134 for its first cycle (estimate 0.000014).
- Seed: 5 lenders deposited; the seed's allocation cycle then stopped because the allocator had
  no gas yet (the seed calls the bot before borrowers). After the allocator was funded (0.002
  ETH, approved by the team in chat), the rest of the seed ran (allocation cycle: 3 transactions,
  4 reason cards; 6 borrowers, 1,233,445 simulated USDG borrowed), without depositing the
  lenders twice.
- One bot cycle afterwards (`bot once`): nothing to change, no transaction, no new reason.
- Reason cards verified onchain: 4 `ReasonLogged` events (seq 1 to 4); for each, the hash
  recomputed from the stored card equals the event's `reasonHash` (`explain/verify.py`).
- Balances after: deployer 0.0066 ETH, allocator 0.00199, curator 0.00042, guardian 0.
- README: one future-work line on using the faucet's real testnet Stock Tokens as collateral.

### 2026-09-27 README testnet row; one-time history copy to Upstash (not run)

- README Deployments: Robinhood Chain testnet row now links the vault and reason registry on the
  testnet explorer (both pages checked, HTTP 200).
- `afterhours state copy-to-shared --profile P [--dry-run]` and `make state-to-upstash
  PROFILE=P` (dry run, then copy): copies local events, reason cards and documents into Upstash
  unchanged; refuses if Upstash already has events or reasons for the profile. Test with the fake
  Upstash: order, timestamps and newest-first reasons kept, locks skipped, second run refused.
- Local `rh-testnet` history to copy: 20 events, 4 reason cards (registry seq 1 to 4), plan and
  forecasts. Waits for the team to say Upstash is ready.
