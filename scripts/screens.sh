#!/usr/bin/env bash
# Screenshot QA for the running web app (make up). PHASE_LABEL overrides the phase label
# ("bell" captures mid-sequence); PAGES lists paths (default "/").
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. scripts/env.sh
base="http://localhost:${WEB_PORT}"  # hardcode-ok: local web
api="http://${API_HOST}:${API_PORT}"  # hardcode-ok: local api
label="${PHASE_LABEL:-$(curl -s "$api/v1/status" | jq -r 'if .state=="open" then "day" else "night" end')}"
# shellcheck disable=SC2086
WEB_BASE_URL="$base" pnpm --filter @afterhours/web exec tsx scripts/screens.ts "$label" ../artifacts/screens ${PAGES:-/}
