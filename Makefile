# Afterhours task runner. Every command in CLAUDE.md lives here.
# Values come from config/afterhours.yaml (via the engine CLI) and .env; nothing is hardcoded.

SHELL := /bin/bash
.DEFAULT_GOAL := help

# Toolchains installed without Homebrew live in the home folder.
export PATH := $(HOME)/.local/bin:$(HOME)/.foundry/bin:$(PATH)

# Load .env.example (non-secret defaults such as ports) then .env, without printing either.
-include .env.example
-include .env
export

PROFILE ?=
ifneq ($(PROFILE),)
export AFTERHOURS_ACTIVE_PROFILE := $(PROFILE)
endif

AH := uv run --quiet afterhours
WEB := pnpm --filter @afterhours/web

.PHONY: help setup gen-schema discover verify-discovered local-chain fork deploy seed engine api web up demo report \
        test test-py test-web test-sol test-config lint lint-py lint-web lint-sol lint-hardcode

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

seed: ## Create simulated lenders and borrowers on the fork
	@echo "make seed arrives with M7." >&2; exit 2

engine: ## Run the data pipeline, model and scheduler
	@echo "make engine arrives with M2 and M6." >&2; exit 2

api: ## Start the FastAPI service
	@echo "make api arrives with M6." >&2; exit 2

web: ## Start the Next.js app
	@NEXT_PUBLIC_API_BASE_URL="$${NEXT_PUBLIC_API_BASE_URL:-http://$${API_HOST}:$${API_PORT}}" $(WEB) exec next dev --port "$${WEB_PORT}"  # hardcode-ok: local scheme

up: ## Everything above for the fork profile, in order
	@echo "make up arrives with M7." >&2; exit 2

demo: ## make up plus the scripted closing-bell scenario
	@echo "make demo arrives with M7." >&2; exit 2

report: ## Regenerate gap stats, model report card and backtest artifacts
	@echo "make report arrives with M2 to M4." >&2; exit 2

# ---------------------------------------------------------------- quality

test: test-py test-web test-sol test-config ## All tests

test-py:
	uv run pytest

test-web:
	$(WEB) test

test-sol:
	@if ls contracts/test/*.t.sol >/dev/null 2>&1; then cd contracts && forge test; \
	else echo "forge: no Solidity tests yet (M5)"; cd contracts && forge build; fi

test-config:
	./scripts/config-roundtrip.sh

lint: lint-py lint-web lint-sol lint-hardcode ## All linters

lint-py:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

lint-web:
	$(WEB) lint
	$(WEB) format:check

lint-sol:
	cd contracts && forge fmt --check

lint-hardcode: ## Fail on addresses or URLs outside config/ and deployments/
	./scripts/lint-hardcode.sh
