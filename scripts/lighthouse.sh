#!/usr/bin/env bash
# Lighthouse on the production build (docs/DESIGN.md: performance >= 85, accessibility >= 95).
# Needs make up running (API). Builds the web app, serves it on WEB_PREVIEW_PORT, audits each
# page in PAGES (default: all) and writes artifacts/lighthouse/<page>.json.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. scripts/env.sh
api="http://${API_HOST}:${API_PORT}"  # hardcode-ok: local api
base="http://localhost:${WEB_PREVIEW_PORT}"  # hardcode-ok: local preview
pages=${PAGES:-"/ /vault /almanac /ledger /replay /report-card"}
min_perf=${LH_MIN_PERF:-85}
min_a11y=${LH_MIN_A11Y:-95}
NEXT_PUBLIC_API_BASE_URL="$api" pnpm --filter @afterhours/web exec next build >/dev/null
NEXT_PUBLIC_API_BASE_URL="$api" pnpm --filter @afterhours/web exec next start --port "$WEB_PREVIEW_PORT" >/dev/null 2>&1 &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT
for _ in $(seq 60); do curl -sf "$base/" >/dev/null && break; sleep 1; done
mkdir -p artifacts/lighthouse
# Lighthouse drives Playwright's Chromium unless CHROME_PATH points at another Chrome.
CHROME_PATH=${CHROME_PATH:-$(cd web && node -e 'console.log(require("@playwright/test").chromium.executablePath())')}
export CHROME_PATH
fail=0
for p in $pages; do
  name=$([ "$p" = "/" ] && echo landing || echo "${p#/}" | tr / -)
  out="artifacts/lighthouse/$name.json"
  pnpm --filter @afterhours/web exec lighthouse "$base$p" --quiet --output=json --output-path="$PWD/$out" \
    --only-categories=performance,accessibility,best-practices --chrome-flags="--headless=new" >/dev/null
  read -r perf a11y bp < <(jq -r '[.categories.performance.score, .categories.accessibility.score, .categories["best-practices"].score] | map(. * 100 | round) | @tsv' "$out")
  echo "$name performance $perf accessibility $a11y best-practices $bp"
  if [ "$perf" -lt "$min_perf" ] || [ "$a11y" -lt "$min_a11y" ]; then fail=1; fi
done
exit $fail
