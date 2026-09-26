# Afterhours: product and technical spec

This is the source of truth for what we build. If code and this file disagree, fix the code or update this file in the same commit with a reason.

## 1. The problem

Robinhood Stock Tokens trade 24/7 on Robinhood Chain and can be posted as collateral in Morpho lending markets. The stocks behind them trade roughly 6.5 hours a day, 5 days a week. When the stock market is closed, the token price can drift from the real share and there is no efficient arbitrage. Lenders face two bad settings:

- aggressive loan-to-value all week: more yield, but bad debt when a stock gaps down after a weekend or an earnings night;
- conservative loan-to-value all week: safe, but capital wasted most of the week.

Afterhours is aggressive when the market is open and calm, and moves lender money to safer markets before the market closes into risk. It does this per stock, automatically, and explains every move.

## 2. Users

| User | Wants | Gets from Afterhours |
| --- | --- | --- |
| Lender | Yield on USDG without watching charts at 2 AM on Saturday | Deposit once; the vault de-risks itself and explains why |
| Borrower | Cash against Stock Tokens without selling | More USDG available on calm days; the normal Morpho borrow flow |
| Other curators, protocols, trading agents (later) | A trustworthy gap-risk score | A paid risk-score API |

## 3. What makes it stand out (build all of these)

1. **Market-hours-aware protocol and interface.** The product literally knows when Wall Street is closed. The UI shifts between Day (exchange open) and Night (afterhours) from the real NYSE calendar, and the closing bell triggers the signature animation that also shows the vault de-risking.
2. **Calibrated risk with a public report card.** We publish predicted vs observed tail coverage, per segment. Almost no DeFi risk product proves its own calibration.
3. **Onchain-verifiable reasons.** Every move has a plain-English reason card. The browser recomputes its hash and checks it against the registry event: a "Verify on chain" button that actually verifies.
4. **Replay theatre.** Pick a real historical earnings night or weekend; watch an ordinary vault and Afterhours side by side on real stock prices.
5. **Risk almanac.** A forward calendar of closed periods and earnings with the predicted bad-case move for each stock.

## 4. Architecture

```
 Inputs                    Afterhours server (off-chain)                     Onchain (Robinhood Chain / Arbitrum)
 --------                  -----------------------------                     ------------------------------------
 Stock prices,  ----+
 earnings, VIX      |      +----------------- Risk engine -----------------+
                    +----> | data -> features -> gap model -> calibration  |      +-------------------+
 Chain data:        |      |                    -> policy (LP) -> explainer |----->| Afterhours Vault  |
 pools, oracle, ----+      +-------------------------------------------------+      | (Morpho vault)    |
 markets, vault                 |                         |                         +---------+---------+
                                v                         v                                   |
                        +---------------+         +---------------+                           v
                        | Allocator bot |-------->| Reason log API|              +-------------------------+
                        | (web3.py)     |  hash   +-------+-------+              | Morpho markets, 2 tiers |
                        +-------+-------+                 |                      | per Stock Token + idle  |
                                |  logReason()            v                      +------------+------------+
                                +----------------> AfterhoursReasonRegistry                   |
                                                          |                                   v
                                                    +-----+------+              Chainlink feeds, Uniswap pools
                                                    | Web app    |<---- SSE / REST ----
                                                    +------------+
```

Trust boundary: the allocator key can only move unborrowed money between markets the vault already approved, reorder where new deposits go, and log reasons. Only the curator (a multisig, simulated by a separate key on the fork) can approve markets or raise caps, and raises wait for the vault timelock. A compromised server can make a bad allocation among approved markets; it cannot take funds.

### Repository layout

```
afterhours/
  CLAUDE.md  PROGRESS.md  README.md  Makefile  docker-compose.yml  .env.example
  config/afterhours.yaml  config/schema.json (generated)
  deployments/<profile>.json  deployments/<profile>.discovered.json
  contracts/            Foundry: src/, script/, test/, lib/ (morpho, openzeppelin via forge install)
  engine/afterhours/    config.py, data/, universe/, features/, model/, policy/, explain/, bot/, sim/, api/, cli.py
  engine/tests/
  backtest/             replay + economics simulator, scenario selection
  web/                  Next.js app (see DESIGN.md)
  ops/kaggle/           only if ever needed
  artifacts/            generated reports, figures, screenshots (committed when small)
  data/cache/           git-ignored
  updates/              builder update drafts
  docs/                 SPEC.md, DESIGN.md, findings/
```

## 5. Configuration model

`config/afterhours.yaml` holds structure and defaults; values unknown until discovery are `null` and must be filled by M1 (with evidence), never guessed. Sketch (names are binding, values are illustrative):

```yaml
active_profile: fork

profiles:
  fork:
    chain: robinhood
    rpc_env: RH_MAINNET_RPC_URL        # name of the env var holding the upstream RPC
    fork_block: null                    # set in M1 to a verified recent block
    local_rpc_port_env: ANVIL_PORT
    oracle_mode: chainlink              # chainlink | simulated (simulated only for replay/demo markets)
    collateral_mode: native             # native | simulated (fallback if Stock Token transfers are restricted)
  rh-testnet: { chain: robinhood-testnet, rpc_env: RH_TESTNET_RPC_URL, oracle_mode: simulated, collateral_mode: simulated }
  rh-mainnet: { chain: robinhood, rpc_env: RH_MAINNET_RPC_URL, oracle_mode: chainlink, collateral_mode: native, requires_human_go: true }
  arb-sepolia: { chain: arbitrum-sepolia, rpc_env: ARB_SEPOLIA_RPC_URL, oracle_mode: simulated, collateral_mode: simulated }
  arb-one: { chain: arbitrum, rpc_env: ARB_ONE_RPC_URL, oracle_mode: chainlink, collateral_mode: native, requires_human_go: true }

chains:                                  # every value filled and verified in M1
  robinhood: { chain_id: null, explorer_url: null, explorer_api_url: null }
  robinhood-testnet: { chain_id: null, explorer_url: null, explorer_api_url: null, faucet_url: null }
  arbitrum: { chain_id: null, explorer_url: null }
  arbitrum-sepolia: { chain_id: null, explorer_url: null, faucet_url: null }

morpho:
  source: discovered                     # discovered | self-deployed (fallback)
  vault_kind: null                       # metamorpho | vault-v2, decided in M1
  lltv_tiers: { weekday: null, weekend: null }   # chosen from Morpho's enabled LLTV list
  liquidation_incentive: { verify_from: "morpho-blue ConstantsLib + MathLib" }

vault:
  name: Afterhours USDG
  symbol: ahUSDG
  performance_fee_bps: 1000
  timelock_seconds: null                 # smallest value the vault allows, from source
  max_share_per_stock: 0.35
  depth_multiplier: 0.5                  # exposure per stock <= multiplier * pool depth at max_slippage
  max_slippage: 0.02

universe:
  onchain_selection: { max_tokens: 5, min_pool_depth_usd: 250000 }
  training_universe_source: sp500        # sp500 | explicit
  training_universe_url_env: null        # or a URL in config if a public list is used
  explicit_tickers: []
  history_start: "2010-01-01"

data:
  providers: [yfinance, stooq, alphavantage]   # tried in order, cached
  earnings_providers: [yfinance, finnhub, alphavantage]
  exchange_calendar: XNYS
  cache_dir: data/cache

model:
  quantiles: [0.01, 0.05]
  target_alpha: 0.01                     # the bad case the policy uses
  conformal: { method: cqr, mondrian_segments: [earnings, weekend, holiday, overnight] }
  lightgbm: { num_leaves: 31, learning_rate: 0.05, n_estimators: 800, min_child_samples: 50 }
  walk_forward: { train_years: 6, calibrate_years: 1, test_years: 1 }

policy:
  safety_margin: 0.02
  turnover_penalty: 0.0005
  min_rebalance_usd: 1000

schedule:
  hourly: true
  pre_close_minutes: 120
  post_open_minutes: 30
  pre_earnings_hours: 24
  triggers: { shock_move_pct: 0.03, shock_window_min: 15, divergence_pct: 0.02, stale_minutes: 90 }

api: { host_env: API_HOST, port_env: API_PORT, cors_origins_env: CORS_ORIGINS, admin_token_env: ADMIN_TOKEN }
web: { api_base_url_env: NEXT_PUBLIC_API_BASE_URL, walletconnect_project_id_env: NEXT_PUBLIC_WC_PROJECT_ID }
alerts: { webhook_env: ALERT_WEBHOOK_URL }
```

Numeric defaults above are starting points to be tuned in M4. Record the final values and why in PROGRESS.md.

## 6. Onchain design

### 6.1 Discovery and verification (M1)

Find, verify with `cast`, and record with source URLs:

- chain ids, public RPC endpoints, explorers and faucets for Robinhood Chain mainnet and testnet, Arbitrum One and Arbitrum Sepolia;
- Morpho core contract, the vault factory in use (MetaMorpho or Vaults V2), the Adaptive Curve IRM, the Chainlink oracle factory for Morpho, and the enabled LLTV list;
- USDG address and decimals;
- the list of Stock Tokens with a Chainlink feed and a Uniswap pool; pick up to `max_tokens` by pool depth;
- existing Morpho markets for those tokens, if any, and their parameters.

Three facts decide the design, answer them explicitly in PROGRESS.md:

1. **Weekend oracle behaviour.** Read feed update events across the last several weekends. Does the Stock Token feed freeze at Friday close, keep updating from a 24/7 source, or something else?
2. **Transfer restrictions.** Can Stock Tokens be transferred to an arbitrary contract (Morpho) and between fork accounts? If restricted, set `collateral_mode: simulated` for fork and testnet and deploy a clearly named mock (`sNVDA (sim)`) with matching decimals.
3. **Vault availability.** Is a Morpho vault factory deployed on Robinhood Chain? If not, deploy Morpho's open-source contracts ourselves on the fork (`morpho.source: self-deployed`) and use Arbitrum for the live vault.

### 6.2 Markets and tiers

A Morpho market is (loan token, collateral token, oracle, IRM, LLTV); parameters are immutable. For each selected Stock Token create two markets, `weekday` and `weekend` LLTV tiers, plus the vault's idle position. Market ids are computed from market params exactly as Morpho does and stored in `deployments/<profile>.json`.

Liquidation incentive: verify the formula in Morpho's source (expected form: `min(maxLIF, 1 / (cursor * LLTV + (1 - cursor)))`) and store the resulting allowance `b_t` per tier in the deployment file. Do not use the formula until verified.

### 6.3 Vault and roles

Standard Morpho vault, loan asset USDG. Roles: owner and curator (multisig on real networks, separate throwaway keys on fork), allocator (bot key), guardian or sentinel (separate key). Map these to whichever vault version M1 finds and document the mapping.

De-risk order: (1) reallocate unborrowed USDG out of the weekday market, (2) reorder the supply queue so new deposits avoid it, (3) cut the weekday cap as the emergency brake. Re-risk: reallocate back after the open; file any cap raises early enough to clear the timelock.

### 6.4 Our contracts

`AfterhoursReasonRegistry.sol`

```solidity
interface IAfterhoursReasonRegistry {
    event ReasonLogged(uint256 indexed seq, bytes32 indexed subject, bytes32 reasonHash, string uri, uint64 timestamp);
    event AllocatorSet(address indexed allocator);
    function logReason(bytes32 subject, bytes32 reasonHash, string calldata uri) external; // onlyAllocator
    function setAllocator(address allocator) external;                                   // onlyOwner
    function seq() external view returns (uint256);
}
```

`reasonHash` is `keccak256` of the reason card serialised with RFC 8785 JSON canonicalisation. `subject` is the Morpho market id, or a vault-level constant for vault-wide actions. Full test coverage including access control and event contents.

`SimOracle.sol` (only for `oracle_mode: simulated`): implements Morpho's `IOracle.price()` with the exact scaling Morpho requires (read it from `IOracle.sol` and the oracle factory source; do not assume). Owner-settable price, used for demo shocks and replays. Every market that uses it is labelled "Simulation" everywhere.

`SimStockToken.sol` (only for `collateral_mode: simulated`): minimal ERC20 with the real token's decimals and a `(sim)` suffix in name and symbol.

### 6.5 Fork seeding

`make seed` creates N lenders and M borrowers from config. Borrower LTVs are drawn from a configurable distribution per tier. Native collateral is obtained by impersonating existing holders on the fork; if that fails, fall back per 6.1.

## 7. Risk engine

### 7.1 Data

- Provider interface with fallbacks in config order; every download cached to Parquet with a manifest (source, time, rows).
- Daily OHLC for the training universe from `history_start`; VIX; exchange sessions from `pandas_market_calendars` (XNYS).
- Earnings events with timing (before open or after close) from the earnings providers.
- Live chain data: Uniswap pool state and depth for each Stock Token, oracle latest round and timestamps, Morpho market state, vault state.

### 7.2 Dataset

- A **closed period** runs from one session's close to the next session's open (overnight, weekend, holiday).
- **Target**: `g = open_next / close_prev - 1`.
- **Segment**: `earnings` if an earnings event falls inside the period, else `holiday`, `weekend` or `overnight`.
- One row per (ticker, closed period). Features only use information available at `close_prev`. Add a test that fails on any lookahead.

### 7.3 Features

Closed hours ahead; segment one-hot; realised volatility (5, 20, 60 day); ticker's historical gap quantiles (expanding window only); VIX level and 5-day change; sector (if available from the provider); days since last earnings; market-wide return on the last session. Live-only features (token vs oracle drift, pool depth) are used by the policy and triggers, not the trained model, so backtest and live share one model.

### 7.4 Model and calibration

- Baselines: (a) one global empirical quantile per segment, (b) per-ticker expanding empirical quantile per segment, (c) EWMA-volatility normal quantile scaled by closed hours.
- Main model: LightGBM quantile regression for each value in `model.quantiles`, one global model across tickers.
- Calibration: conformalized quantile regression (CQR) with Mondrian conformal by segment, so earnings nights are calibrated on their own.
- Validation: walk-forward folds from `model.walk_forward`. Report per fold and per segment: empirical coverage vs target, pinball loss, and mean interval width.
- Acceptance: on held-out years, coverage for `target_alpha` within 1 percentage point of target overall and within 2 points on the earnings segment, and pinball loss better than every baseline. If not met, ship the best baseline, say so in the report card and README, and keep the model as future work.
- Artifacts: `artifacts/model/report_card.json`, calibration plots, feature importances, saved model with a version hash.

### 7.5 Policy

For every Stock Token `s` and tier `t`, with `q_s` the calibrated bad-case drop for the next closed period, `m` the safety margin and `b_t` the liquidation incentive allowance:

- tier allowed only if `q_s + m <= 1 - LLTV_t - b_t`;
- allocation variables `x_{s,t} >= borrowed_{s,t}` (borrowed money cannot be pulled), `x <= cap_{s,t}`;
- per-stock limit `sum_t x_{s,t} <= min(max_share_per_stock * total, depth_multiplier * depth_s)`;
- `sum x + idle = total`;
- maximise expected supply interest minus `turnover_penalty * |x - x_prev|` (linearised), using each market's current rate; solve with `scipy.optimize.linprog`.
- Skip execution if the total change is below `min_rebalance_usd`.

### 7.6 Triggers and schedule

APScheduler jobs built from the exchange calendar and `schedule` config: hourly, pre-close, post-open, pre-earnings. Event triggers: token move above `shock_move_pct` within `shock_window_min`; token vs oracle divergence above `divergence_pct`; oracle older than `stale_minutes` while the market is open. Every run writes a plan; only changed plans execute.

### 7.7 Reason cards

```json
{
  "id": "uuid",
  "created_at": "ISO-8601",
  "profile": "fork",
  "subject": "market id or vault",
  "stock": "ticker",
  "action": "reallocate | cap_cut | queue_reorder | hold",
  "from_tier": "weekday", "to_tier": "weekend", "amount_usdg": "decimal string",
  "closed_period": { "starts": "ISO", "ends": "ISO", "segment": "earnings", "hours": 63 },
  "prediction": { "alpha": 0.01, "bad_case_drop": 0.0, "model_version": "hash" },
  "top_drivers": [{ "feature": "earnings_in_window", "shap": 0.0 }],
  "rule_fired": "plain English sentence",
  "tx": { "chain_id": 0, "reallocate_tx": "0x...", "registry_tx": "0x..." }
}
```

`reasonHash` covers the card without the `tx` block. The API serves the canonical JSON so the browser can recompute the hash.

## 8. API (FastAPI)

| Method and path | Returns |
| --- | --- |
| `GET /v1/health` | Service, chain, model and scheduler health |
| `GET /v1/config/public` | Public config for the web app (profile, chain ids, explorer URLs, deployment addresses) |
| `GET /v1/status` | Session state (open, closed, holiday), next open and close, time until each |
| `GET /v1/vault` | TVL, APY, share price, allocation per market, idle, caps, borrowed |
| `GET /v1/risk` | Per stock: next closed period, calibrated bad-case drop, drivers, allowed tiers |
| `GET /v1/almanac?days=` | Upcoming closed periods and earnings with risk per stock |
| `GET /v1/reasons?cursor=` and `GET /v1/reasons/{id}` | Reason cards, canonical JSON, tx hashes, server-side verification result |
| `GET /v1/report-card` | Model and backtest artifacts |
| `GET /v1/replay/scenarios` and `GET /v1/replay/{id}` | Replay scenarios and their time series for both strategies |
| `POST /v1/sim/close-out`, `POST /v1/sim/shock` | Fork and simulated profiles only, requires the admin token |
| `GET /v1/stream` | Server-sent events: `status`, `plan_changed`, `tx_sent`, `tx_confirmed`, `reason_logged`, `vault_updated` |

## 9. Backtest and replay

- Economics simulator over historical closed periods for the selected tokens' underlying stocks. Borrower LTV distribution per tier and interest rates come from config (documented as assumptions). Liquidation at the next open with the verified incentive; bad debt when collateral cannot cover debt.
- Strategies: always weekday tier, always weekend tier, Afterhours, and a perfect-foresight upper bound.
- Metrics: net lender yield, bad debt, worst single event, share of time in each tier.
- Replay scenarios are selected from the data, not typed in: the top N closed periods by absolute gap for the selected tokens, split by segment, with N and filters in config.
- Output: `artifacts/backtest/*.json` consumed by the report card and replay pages. Always labelled "historical stock prices, simulated vault".

## 10. Milestones (continuous, in order; parallelise where independent)

Each milestone ends with a PROGRESS.md entry, a commit, and a builder update draft.

- [ ] **M0 Bootstrap.** Monorepo, Makefile, uv and pnpm workspaces, Foundry project, config loaders with schema, `.env.example`, `make lint-hardcode`, pre-commit hooks, PROGRESS.md.
  Accept: `make setup`, `make lint`, `make test` pass on this Mac; a config value changed in YAML is visible in both Python and web loaders.
- [ ] **M1 Discovery.** Everything in 6.1, including the three deciding facts.
  Accept: `deployments/fork.discovered.json` with evidence for every address; a `cast`-based verification script passes; decisions recorded.
- [ ] **M2 Data and gap study.** Providers, cache, universe, dataset, lookahead test.
  Accept: `artifacts/gaps/summary.json` and figures with the gap distribution by segment for the selected tokens. This is slide 1; print the headline numbers in chat.
- [ ] **M3 Model.** Baselines, LightGBM, CQR with Mondrian segments, walk-forward.
  Accept: `report_card.json` meets 7.4 or the fallback is applied and stated.
- [ ] **M4 Policy and backtest.** LP policy and economics simulator; tune the config defaults.
  Accept: backtest artifacts for all four strategies; tuned values recorded with reasons.
- [ ] **M5 Contracts.** Registry, sim contracts, deploy scripts for markets and vault with roles, full tests, fork tests.
  Accept: `forge test` green including fork tests; `make deploy PROFILE=fork` writes `deployments/fork.json`.
- [ ] **M6 Bot and API.** Allocator executing plans, reason cards with registry logging, scheduler and triggers, FastAPI with SSE, Typer CLI.
  Accept: on the fork, a forced close-out moves funds exactly as planned, the registry event matches the recomputed hash, and SSE emits every event type.
- [ ] **M7 Simulation harness.** Seeding, scripted scenarios (closing bell, earnings shock, oracle drift), `make demo`.
  Accept: `make demo` runs the closing-bell scenario end to end without manual steps.
- [ ] **M8 Frontend foundation.** Design tokens, fonts, day/night engine, illustration system, layout, wallet connect, API client.
  Accept: screenshots at three widths in both modes reviewed and saved; Lighthouse targets met on a stub landing.
- [ ] **M9 Frontend pages.** Landing, Vault, Almanac, Ledger, Replay, Report card, all on live API data.
  Accept: every page reviewed by screenshot loop; deposit and withdraw work on the fork; Verify on chain works.
- [ ] **M10 End-to-end hardening.** Playwright E2E through the whole demo, error and empty states, reduced motion, mobile.
  Accept: E2E green; clean-clone run of `make demo` documented.
- [ ] **M11 Live deployments.** Robinhood Chain testnet and Arbitrum Sepolia (and mainnet only with a human go); hosted API and web.
  Accept: addresses and links in README; the hosted app reads the live testnet deployment.
- [ ] **M12 Submission assets.** README with architecture and run guide, demo script and shot list for the two videos, final report numbers, all builder update drafts.
  Accept: a checklist in PROGRESS.md covering every Colosseum submission field.

## 11. Fallbacks

| If | Then |
| --- | --- |
| Morpho vault factory not on Robinhood Chain | Self-deploy Morpho open-source contracts on the fork; live vault on Arbitrum |
| Stock Token transfers restricted | `collateral_mode: simulated` on fork and testnet, labelled |
| No usable Chainlink feed for a token | Skip that token; if none usable, `oracle_mode: simulated` for the demo, labelled |
| Price provider rate-limited or down | Next provider in config; cached data first |
| Model misses acceptance | Ship best baseline; state it plainly |
| Weekend gaps small for mega-caps | Emphasise earnings segment and smaller-cap tokens in the story |
| Testnet faucet dry | Fork-only demo plus Arbitrum Sepolia, stated in README |

## 12. Out of scope

Our own lending protocol, our own oracle network, a governance token, a trading bot, custody of real user funds, and any claim of legal eligibility for Stock Tokens in a given country.
