# Afterhours progress

## BLOCKED

Nothing yet.

## Milestones

- [x] M0 Bootstrap (2026-09-26, `d185414`)
- [ ] M1 Discovery
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
