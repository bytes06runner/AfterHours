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
- [ ] M2 Data and gap study
- [ ] M3 Model
- [ ] M4 Policy and backtest
- [ ] M5 Contracts
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
