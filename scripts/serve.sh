#!/usr/bin/env bash
# Hosted engine entry point (Render; docs/HOSTING.md). One process tree on one disk:
#   - the API in the foreground, bound to 0.0.0.0 and the PORT the host provides;
#   - in the background: refresh every Stock Token's prices, then the allocator bot (when the
#     active profile has a deployment and ALLOCATOR_PK is set) and the Telegram alerts (when
#     TELEGRAM_BOT_TOKEN is set). Each is restarted if it exits.
# Persistent paths come from AFTERHOURS_PATHS__STATE_DIR and AFTERHOURS_DATA__CACHE_DIR.
set -euo pipefail
cd "$(dirname "$0")/.."

export API_HOST="${API_HOST:-0.0.0.0}"  # hardcode-ok: every Render web service binds 0.0.0.0
export API_PORT="${PORT:-${API_PORT:?set PORT (the host sets it) or API_PORT}}"
AH=(uv run --frozen --no-dev afterhours)
RESTART_SECONDS="${RESTART_SECONDS:-30}"

log() { echo "serve: $*" >&2; }

keep() { # keep NAME CMD...: run CMD, restart it after it exits
  local name=$1
  shift
  while true; do
    "$@" || log "$name exited ($?)"
    log "restarting $name in ${RESTART_SECONDS}s"
    sleep "$RESTART_SECONDS"
  done
}

background() {
  "${AH[@]}" data fetch --stock-tokens >/dev/null || log "price refresh failed; using cached prices"
  local profile deployment
  profile=$("${AH[@]}" config get active_profile | tr -d '"')
  deployment="deployments/${profile}.json"
  if [ -n "${ALLOCATOR_PK:-}" ] && [ -f "$deployment" ]; then
    keep bot "${AH[@]}" bot run &
  else
    log "bot not started: needs ALLOCATOR_PK and $deployment (docs/HOSTING.md)"
  fi
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    keep alerts "${AH[@]}" alerts run &
  else
    log "alerts not started: TELEGRAM_BOT_TOKEN is not set"
  fi
  wait
}

background &
exec "${AH[@]}" api
