# Afterhours task runner. Every command in CLAUDE.md lives here.
# Values come from config/afterhours.yaml (via the engine CLI) and .env; nothing is hardcoded.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Toolchains installed without Homebrew live in the home folder.
export PATH := $(HOME)/.local/bin:$(HOME)/.foundry/bin:$(PATH)

# Load .env, then .env.example for anything still unset, without printing either. Variables
# already in the environment win (tests and callers pass their own ports), hence ?= and not an
# include, which would override them.
define _newline


endef
$(eval $(subst ;;,$(_newline),$(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=\(.*\)$$/\1 ?= \2;;/p' .env .env.example 2>/dev/null)))
export

PROFILE ?=
ifneq ($(PROFILE),)
export AFTERHOURS_ACTIVE_PROFILE := $(PROFILE)
endif

AH := uv run --quiet afterhours
WEB := pnpm --filter @afterhours/web

NAME ?= closing_bell

.PHONY: help setup scenario gen-schema discover verify-discovered local-chain screens lighthouse e2e fork deploy seed engine api web up demo report \
        test test-py test-web test-sol test-config test-integration lint lint-py lint-web lint-sol lint-hardcode lint-numbers

help: ## List commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install toolchains and dependencies (uv, pnpm, foundry libs)
	@command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh  # hardcode-ok: installer
	@command -v forge >/dev/null || (curl -L https://foundry.paradigm.xyz | bash && $(HOME)/.foundry/bin/foundryup)  # hardcode-ok: installer
	@command -v pnpm >/dev/null || npm install -g pnpm@9
	uv python install 3.12
	uv sync
	./scripts/link-libomp.sh
	pnpm install
	git submodule update --init --recursive
	git config core.hooksPath .githooks
	cd contracts && forge build
	@test -f .env || echo "Next: cp .env.example .env and fill it in (see KICKOFF.md section 3)."

gen-schema: ## Regenerate config/schema.json from the pydantic model
	$(AH) config schema

discover: ## M1: find and verify protocol addresses, write deployments/<profile>.discovered.json
	$(AH) discover

verify-discovered: ## Re-check the discovered file with plain cast calls
	./scripts/verify-discovered.sh

# ---------------------------------------------------------------- stack (later milestones)

fork: ## Start Anvil forking the active profile's chain at the configured block (needs an archive RPC)
	@rpc_env=$$($(AH) config get profiles.fork.rpc_env | tr -d '"'); \
	block=$$($(AH) config get profiles.fork.fork_block); \
	[ -n "$${!rpc_env}" ] || { echo "set $$rpc_env in .env to an archive RPC (see PROGRESS.md BLOCKED)" >&2; exit 1; }; \
	anvil --fork-url "$${!rpc_env}" --fork-block-number "$$block" --port "$${ANVIL_PORT}"

local-chain: ## Start a plain local Anvil chain for the local profile (simulation)
	anvil --port "$${ANVIL_PORT}"

deploy: ## Deploy markets, vault, registry; write deployments/<profile>.json
	$(AH) deploy

scenario: ## Run a scripted scenario on the running local stack: NAME=closing_bell | earnings_shock | oracle_drift
	$(AH) sim scenario $(NAME)

seed: ## Create simulated lenders and borrowers (Anvil, or testnets with simulated tokens)
	$(AH) sim seed

engine: ## Refresh market data (cached) and run the bot scheduler
	$(AH) data build >/dev/null
	$(AH) bot run

api: ## Start the FastAPI service
	$(AH) api

web: ## Start the Next.js app
	@NEXT_PUBLIC_API_BASE_URL="$${NEXT_PUBLIC_API_BASE_URL:-http://$${API_HOST}:$${API_PORT}}" $(WEB) exec next dev --port "$${WEB_PORT}"  # hardcode-ok: local scheme

up: ## Chain, deploy, seed, API, bot and web for the demo profile, in order (no scenario)
	DEMO_SKIP_SCENARIO=1 ./scripts/demo.sh

demo: ## make up plus the scripted closing-bell scenario
	./scripts/demo.sh

report: ## Regenerate gap stats, model report card and backtest artifacts
	$(AH) gaps
	$(AH) model
	$(AH) backtest

# ---------------------------------------------------------------- quality

test: test-py test-web test-sol test-config test-integration ## All tests

test-py:
	uv run pytest

test-web:
	$(WEB) test

test-sol:
	@if ls contracts/test/*.t.sol >/dev/null 2>&1; then cd contracts && forge test; \
	else echo "forge: no Solidity tests yet (M5)"; cd contracts && forge build; fi

test-config:
	./scripts/config-roundtrip.sh

test-integration: ## Deploy, seed and run the API on a throwaway Anvil chain (M6 acceptance)
	uv run pytest -m integration engine/tests/integration -q

lint: lint-py lint-web lint-sol lint-hardcode lint-numbers ## All linters

lint-py:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

lint-web:
	$(WEB) lint
	$(WEB) format:check

lint-sol:
	cd contracts && forge fmt --check

e2e: ## Playwright E2E against the running stack (make up); E2E_ARGS passes playwright options
	./scripts/e2e.sh $(E2E_ARGS)

lighthouse: ## Lighthouse on the production build for every page (needs make up running)
	./scripts/lighthouse.sh

screens: ## Screenshot QA of pages at 1440/1024/390 in the current phase (needs make up running)
	./scripts/screens.sh

lint-numbers: ## README and video scripts quote only numbers from artifacts/report/numbers.json
	python3 scripts/check-numbers.py

lint-hardcode: ## Fail on addresses or URLs outside config/ and deployments/
	./scripts/lint-hardcode.sh
