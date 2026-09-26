#!/usr/bin/env bash
# make demo: chain at the demo start time, deploy, seed, API, bot scheduler, web app, then the
# scripted closing-bell scenario. Everything on the local profile is labelled Simulation.
# DEMO_EXIT=1 stops everything after the scenario (used by tests); otherwise Ctrl-C to stop.
# DEMO_SKIP_WEB=1 leaves out the web app (tests; a second next dev would share web/.next).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export PATH="$HOME/.local/bin:$HOME/.foundry/bin:$PATH"
. scripts/env.sh

AH="uv run --quiet afterhours"
export AFTERHOURS_ACTIVE_PROFILE="${AFTERHOURS_ACTIVE_PROFILE:-$($AH config get demo.profile | tr -d '"')}"
profile="$AFTERHOURS_ACTIVE_PROFILE"
start=$($AH config get demo.start | tr -d '"')
start_ts=$(uv run --quiet python -c "from datetime import datetime; print(int(datetime.fromisoformat('$start'.replace('Z','+00:00')).timestamp()))")
state_dir=$($AH config get paths.state_dir | tr -d '"')/$profile
mkdir -p "$(dirname "$state_dir")"

if [ -z "${ADMIN_TOKEN:-}" ]; then
  mkdir -p data/cache
  [ -f data/cache/admin-token ] || (umask 077; openssl rand -hex 32 > data/cache/admin-token)
  ADMIN_TOKEN=$(cat data/cache/admin-token); export ADMIN_TOKEN
fi

pids=()
cleanup() { for p in "${pids[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT

rm -rf "$state_dir"
echo "demo: profile $profile, chain clock starts at $start"
if [ "$profile" = "local" ]; then
  anvil --port "$ANVIL_PORT" --timestamp "$start_ts" --silent & pids+=($!)
else
  make fork & pids+=($!)
fi
for _ in $(seq 60); do cast chain-id --rpc-url "http://127.0.0.1:$ANVIL_PORT" >/dev/null 2>&1 && break; sleep 1; done  # hardcode-ok: local node

$AH data fetch >/dev/null  # the vault stocks' prices and earnings (cached after the first run)
$AH deploy
$AH sim seed
$AH api >"$state_dir.api.log" 2>&1 & pids+=($!)
$AH bot run >"$state_dir.bot.log" 2>&1 & pids+=($!)
api="http://$API_HOST:$API_PORT"  # hardcode-ok: scheme only
if [ -d web/node_modules ] && [ "${DEMO_SKIP_WEB:-0}" != "1" ]; then
  NEXT_PUBLIC_API_BASE_URL="$api" pnpm --filter @afterhours/web exec next dev --port "$WEB_PORT" \
    >"$state_dir.web.log" 2>&1 & pids+=($!)
fi
for _ in $(seq 60); do curl -sf "$api/v1/health" >/dev/null && break; sleep 1; done

if [ "${DEMO_SKIP_SCENARIO:-0}" != "1" ]; then
  echo "demo: running the closing-bell scenario"
  $AH sim scenario closing_bell | tee "$state_dir.closing_bell.json"
fi
echo "demo: API $api   web http://localhost:$WEB_PORT   (Simulation)"  # hardcode-ok: local web
if [ "${DEMO_EXIT:-0}" = "1" ]; then exit 0; fi
echo "demo: running; press Ctrl-C to stop"
wait
