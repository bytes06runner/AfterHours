# Afterhours

Afterhours is an ML risk-curated lending vault for Robinhood Stock Tokens. Lenders deposit USDG into a Morpho vault. A calibrated gap-risk model moves unborrowed capital between tiered Morpho markets before weekends, holidays and earnings, when the real stock market is closed but Stock Tokens keep trading. Every move is explained in plain English and its hash is anchored onchain.

Hackathon: Colosseum Crypto World's Fair. Tracks: Robinhood Chain (primary) and Arbitrum (same code).
Hard deadline: 2026-10-12 23:59 PDT. Target submission: 2026-10-11.

Read these before doing anything, and re-read the relevant one before each milestone:

- @docs/SPEC.md : product and technical spec, milestones, fallbacks. Source of truth.
- @docs/DESIGN.md : UI/UX system. Source of truth for everything visual.
- @PROGRESS.md : what is done, what is next, what is blocked. Create it on first run.

## Operating mode: build continuously

1. Work through the milestones in SPEC.md in order, starting at the first unchecked one in PROGRESS.md. Independent work may run in parallel through the subagents in `.claude/agents/`.
2. For each milestone: short plan, implement, write tests, run them, fix until green, check every acceptance criterion, record the result, commit, then start the next milestone immediately.
3. After every result (a finished milestone, or a meaningful measured result inside one, such as the gap statistics, model coverage, or the first successful fork reallocation):
   - append an entry to PROGRESS.md: what was done, evidence (command run and a summary of its output or metrics), files touched, screenshots if UI, what is next;
   - print a 3 to 5 line summary in chat;
   - write a draft Colosseum builder update to `updates/YYYY-MM-DD-<slug>.md` (plain, human tone, under 150 words, no hype).
4. Do not stop to ask permission for routine work. Stop only when:
   - a credential, account or key that only the human can create is missing;
   - an onchain or external fact fails verification and SPEC.md gives no fallback;
   - a decision would change the product's scope or the claims we make to judges.
   When blocked, write the question under `## BLOCKED` at the top of PROGRESS.md, finish any other unblocked work first, then end the turn.
5. When resuming a session, read PROGRESS.md first and continue from where it says.

## Hard rules

### No hardcoding

- Every address, chain id, RPC URL, token, ticker, threshold, LLTV tier, fee, schedule time, model hyperparameter, file path, port and external URL lives in configuration:
  - `config/afterhours.yaml` for non-secret values, organised by profile (`fork`, `rh-testnet`, `rh-mainnet`, `arb-sepolia`, `arb-one`);
  - `.env` for secrets and for the names of per-machine values. `.env.example` lists every variable with a comment, never a real value.
- One typed loader per language: `engine/afterhours/config.py` (pydantic-settings, validated against a JSON Schema generated from the model) and `web/src/lib/config.ts` (zod). The web app gets public config from `GET /v1/config/public` or build-time env, never from literals.
- Addresses from our own deployments are written to `deployments/<profile>.json`. Addresses we discover (Morpho, USDG, Stock Tokens, feeds, pools) go to `deployments/<profile>.discovered.json`, each with its source URL and verification evidence. Bot, API and web read only from these files.
- Allowed literals: math constants, protocol constants copied from verified source code with a comment linking that source, and test fixtures.
- `make lint-hardcode` greps for 40-hex addresses and http(s) URLs outside `config/`, `deployments/`, `tests/`, `docs/` and fails the build if it finds any. Keep it green.

### Truth and verification

- Never invent a contract address, ABI, chain id, API endpoint or protocol parameter. Find it in official documentation (use the Context7 MCP and web fetch), then verify it onchain with `cast` (bytecode exists, `symbol()`, `decimals()`, expected view calls) before using it. Record the evidence.
- If something cannot be verified, use the fallback listed in SPEC.md and label the affected feature as simulated in the UI and README.
- Anything simulated is labelled "Simulation" in the UI. Backtests say "historical stock prices, simulated vault".
- Never show or claim a number we did not measure. Every number in the UI, README or pitch comes from a generated file in `artifacts/`.

### Secrets and safety

- Never read, print or commit `.env`, `.env.local` or anything in `secrets/`. Use `.env.example` to learn variable names.
- Only use throwaway keys created with `cast wallet new`, funded with testnet or fork ETH. Never request or use a key that holds real funds.
- Any mainnet deployment needs an explicit human "go" written in PROGRESS.md first.
- No `git push --force`. Never delete files outside this repository.

### Compute

- Default: run everything locally on this MacBook Air (Apple Silicon, arm64). Prefer native arm64 builds. LightGBM needs `brew install libomp`.
- Before any job you expect to take more than 20 minutes locally or to need more than 12 GB of RAM, write a quick estimate into PROGRESS.md. Only if it is truly heavy, create a Kaggle kernel in `ops/kaggle/<job>/` (notebook, `kernel-metadata.json`, a dataset upload script using the Kaggle CLI), push it, poll it, and download outputs into `artifacts/`. Expected outcome: not needed, because the dataset is small. Prove it with the estimate.
- Large downloads (toolchains, Docker images, datasets) are fine. Cache data in `data/cache/` (git-ignored).

### Code quality

- Python 3.12 managed with uv; ruff and mypy (strict for `engine/afterhours`); pytest.
- TypeScript strict; eslint; prettier; vitest; Playwright for end-to-end tests.
- Solidity with Foundry; `forge fmt`; fork tests pinned to a block number taken from config.
- Small modules, typed interfaces, docstrings on public functions. Conventional commit messages.
- All writing (UI copy, docs, commits, updates): plain and human, sentence case, no em dashes, no hype words ("revolutionary", "seamless", "unlock").

### Frontend quality bar

- Follow docs/DESIGN.md exactly. The UI is illustrated, animated and crafted, never minimal. Every animation must mean something.
- After every UI change: run the app, take screenshots with the Playwright MCP at 1440, 1024 and 390 px wide, in day and night mode; look at them; critique them against DESIGN.md; fix; screenshot again. Save final shots in `artifacts/screens/`.
- Landing page Lighthouse: performance at least 85, accessibility at least 95. `prefers-reduced-motion` is respected everywhere.

## Commands (keep all of these working)

| Command | Does |
| --- | --- |
| `make setup` | Installs toolchains and dependencies (uv, pnpm, foundry libs) |
| `make fork` | Starts Anvil forking the chain of the active profile at the configured block |
| `make deploy PROFILE=<p>` | Deploys markets, vault, registry; writes `deployments/<p>.json` |
| `make seed` | Creates simulated lenders and borrowers on the fork |
| `make engine` | Runs the data pipeline, model and scheduler |
| `make api` | Starts the FastAPI service |
| `make web` | Starts the Next.js app |
| `make up` | Everything above for the `fork` profile, in the right order |
| `make demo` | `make up` plus the scripted closing-bell scenario |
| `make report` | Regenerates gap stats, model report card and backtest artifacts |
| `make test` / `make lint` / `make lint-hardcode` | All tests, all linters, the hardcoding check |

## Definition of done

From a clean clone, after `make setup` and filling `.env`, `make demo` brings up the forked chain, deployed markets, vault and registry, seeded lenders and borrowers, the engine and bot on schedule, the API and the web app. A scripted closing-bell scenario shows the bot de-risking, a reason card anchored onchain and verified in the browser, and the UI updating live. Testnet deployments exist on Robinhood Chain and Arbitrum with addresses in the README. All tests and linters pass.
