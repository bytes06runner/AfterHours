#!/usr/bin/env bash
# Proves a value changed in YAML is visible to both the Python and the web loader.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
marker="ahRT$RANDOM"
sed -E "s/^(  symbol: ).*/\1${marker}/" config/afterhours.yaml > "$tmp/afterhours.yaml"

export AFTERHOURS_CONFIG="$tmp/afterhours.yaml"
py=$(uv run --quiet afterhours config get vault.symbol)
web=$(uv run --quiet afterhours config public | pnpm --silent --filter @afterhours/web print-config vault.symbol)

expected="\"${marker}\""
if [ "$py" != "$expected" ] || [ "$web" != "$expected" ]; then
  echo "config-roundtrip: expected $expected, python=$py web=$web" >&2
  exit 1
fi
echo "config-roundtrip: python and web both see vault.symbol=$expected"
