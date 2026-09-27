#!/usr/bin/env bash
# Hosted engine entry point (Render; docs/HOSTING.md).
#   - The API runs in the foreground, bound to 0.0.0.0 and the PORT the host provides. It warms
#     prices, the risk board and the borrower examples itself, in the same process.
#   - Free setup: that is all. The bot and the pre-close alerts run in GitHub Actions, and
#     Telegram commands arrive at the API's webhook.
#   - Paid setup (render.yaml, one disk): also the allocator bot, when ALLOCATOR_PK is set and the
#     profile has a deployment, and Telegram long polling, when TELEGRAM_BOT_TOKEN is set and no
#     webhook secret is. Each is restarted if it exits.
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
  local profile deployment
  if [ -n "${ALLOCATOR_PK:-}" ]; then
    profile=$("${AH[@]}" config get active_profile | tr -d '"')
    deployment="deployments/${profile}.json"
    if [ -f "$deployment" ]; then
      keep bot "${AH[@]}" bot run &
    else
      log "bot not started: no $deployment yet (docs/HOSTING.md)"
    fi
  else
    log "bot not started here: no ALLOCATOR_PK (free setup runs it in GitHub Actions)"
  fi
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
    keep alerts "${AH[@]}" alerts run &
  else
    log "alert polling not started: webhook mode, or TELEGRAM_BOT_TOKEN is not set"
  fi
  wait
}

background &
exec "${AH[@]}" api
