#!/usr/bin/env bash
# Independent check of deployments/<profile>.discovered.json with plain `cast` calls.
# Uses the profile's RPC env var if set, else the chain's public RPC from config.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export PATH="$HOME/.local/bin:$HOME/.foundry/bin:$PATH"

profile=$(uv run --quiet afterhours config get active_profile | tr -d '"')
file="deployments/${profile}.discovered.json"
[ -f "$file" ] || { echo "verify: $file missing; run afterhours discover" >&2; exit 1; }
chain=$(jq -r '._meta.chain' "$file")
rpc_env=$(uv run --quiet afterhours config get "profiles.${profile}.rpc_env" | tr -d '"')
rpc="${!rpc_env:-}"
[ -n "$rpc" ] || rpc=$(uv run --quiet afterhours config get "chains.${chain}.public_rpc_url" | tr -d '"')

pass=0; fail=0
ok()  { pass=$((pass + 1)); }
bad() { fail=$((fail + 1)); echo "FAIL: $*" >&2; }
expect() { # name actual expected
  if [ "$2" == "$3" ]; then ok; else bad "$1: got '$2' want '$3'"; fi
}

want_chain=$(jq -r '._meta.chain_id' "$file")
expect "chain id" "$(cast chain-id --rpc-url "$rpc")" "$want_chain"

for key in $(jq -r '.core | keys[]' "$file"); do
  addr=$(jq -r ".core.${key}.address" "$file")
  code=$(cast code "$addr" --rpc-url "$rpc")
  if [ "${#code}" -gt 2 ]; then ok; else bad "$key $addr has no code"; fi
done

blue=$(jq -r '.core.morpho_blue.address' "$file")
irm=$(jq -r '.core.adaptive_curve_irm.address' "$file")
usdg=$(jq -r '.core.usdg.address' "$file")
expect "Morpho isIrmEnabled(irm)" "$(cast call "$blue" 'isIrmEnabled(address)(bool)' "$irm" --rpc-url "$rpc")" "true"
expect "IRM MORPHO()" "$(cast call "$irm" 'MORPHO()(address)' --rpc-url "$rpc")" "$blue"
expect "USDG symbol" "$(cast call "$usdg" 'symbol()(string)' --rpc-url "$rpc")" '"USDG"'

for wad in $(jq -r '.lltvs.values_wad[]' "$file"); do
  expect "isLltvEnabled($wad)" "$(cast call "$blue" 'isLltvEnabled(uint256)(bool)' "$wad" --rpc-url "$rpc")" "true"
done

for sym in $(jq -r '.selected[]' "$file"); do
  base=".stock_tokens.${sym}"
  token=$(jq -r "${base}.address" "$file")
  feed=$(jq -r "${base}.feed.address" "$file")
  expect "$sym symbol" "$(cast call "$token" 'symbol()(string)' --rpc-url "$rpc")" "\"$sym\""
  expect "$sym decimals" "$(cast call "$token" 'decimals()(uint8)' --rpc-url "$rpc")" "18"
  desc=$(cast call "$feed" 'description()(string)' --rpc-url "$rpc")
  case "$desc" in *"$sym"*) ok ;; *) bad "$sym feed description '$desc'";; esac
  expect "$sym feed decimals" "$(cast call "$feed" 'decimals()(uint8)' --rpc-url "$rpc")" "8"
  for mid in $(jq -r "${base}.morpho_markets[]?.market_id" "$file"); do
    collat=$(cast call "$blue" 'idToMarketParams(bytes32)(address,address,address,address,uint256)' "$mid" --rpc-url "$rpc" | sed -n 2p)
    expect "$sym market $mid collateral" "$collat" "$token"
  done
done

echo "verify-discovered: $pass passed, $fail failed ($file)"
[ "$fail" -eq 0 ]
