#!/usr/bin/env bash
# Playwright E2E against the running stack (make up). Extra arguments go to playwright.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. scripts/env.sh
export WEB_BASE_URL="http://localhost:${WEB_PORT}"  # hardcode-ok: local web
export API_BASE_URL="http://${API_HOST}:${API_PORT}"  # hardcode-ok: local api
export ANVIL_RPC_URL="http://127.0.0.1:${ANVIL_PORT}"  # hardcode-ok: local node
if [ -z "${ADMIN_TOKEN:-}" ] && [ -f data/cache/admin-token ]; then
  ADMIN_TOKEN=$(cat data/cache/admin-token); export ADMIN_TOKEN
fi
cd web && pnpm exec playwright test "$@"
