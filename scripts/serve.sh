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
# Memory (Render free has 512 MB for the whole service; measured 2026-10-04 via /v1/health):
#   - glibc gives every thread its own malloc arena, and a burst of visitors runs dozens of
#     request threads, so cap the arenas;
#   - run the installed entry point directly: `uv run` stays resident as a parent process.
#   - numeric libraries start one worker thread (with its own buffers) per host core, and the
#     host has many cores even though the service gets a fraction of one, so use one thread.
export MALLOC_ARENA_MAX="${MALLOC_ARENA_MAX:-2}"
for v in OPENBLAS_NUM_THREADS OMP_NUM_THREADS MKL_NUM_THREADS NUMEXPR_NUM_THREADS; do
  export "$v=${!v:-1}"
done
if [ -x .venv/bin/afterhours ]; then
  AH=(.venv/bin/afterhours)
else
  AH=(uv run --frozen --no-dev afterhours)
fi
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
