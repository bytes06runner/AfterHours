#!/usr/bin/env bash
# M11 dress rehearsal: deploy a testnet profile onto an Anvil fork of that testnet at head, with
# throwaway keys from `cast wallet new` funded with fork ETH. Keys live only in this process's
# environment; deployments and state go to a scratch folder, never deployments/. Then one bot
# cycle and the API's vault read against the fork. Usage: rehearse-testnet.sh <profile>
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
. scripts/env.sh
export PATH="$HOME/.local/bin:$HOME/.foundry/bin:$PATH"
profile=${1:?profile, e.g. rh-testnet}
AH="uv run --quiet afterhours"
export AFTERHOURS_ACTIVE_PROFILE="$profile"
chain=$($AH config get "profiles.$profile.chain" | tr -d '"')
rpc_env=$($AH config get "profiles.$profile.rpc_env" | tr -d '"')
upstream="${!rpc_env:-$($AH config get "chains.$chain.public_rpc_url" | tr -d '"')}"
port=$(uv run --quiet python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
work="contracts/cache/rehearsal-$profile-$port"
mkdir -p "$work/deployments" "$work/state"
cp deployments/*.discovered.json "$work/deployments/" 2>/dev/null || true
anvil --fork-url "$upstream" --port "$port" --silent & anvil_pid=$!
trap 'kill $anvil_pid 2>/dev/null || true' EXIT
node="http://127.0.0.1:$port"  # hardcode-ok: local fork
for _ in $(seq 60); do cast chain-id --rpc-url "$node" >/dev/null 2>&1 && break; sleep 1; done
echo "rehearsal: $profile forked at block $(cast block-number --rpc-url "$node"), chain id $(cast chain-id --rpc-url "$node")"
for role in DEPLOYER_PK CURATOR_PK ALLOCATOR_PK GUARDIAN_PK; do
  json=$(cast wallet new --json)
  w='.data | if type == "array" then .[0] else . end'  # cast's JSON shape differs by version
  key=$(jq -r "$w | .private_key" <<<"$json"); addr=$(jq -r "$w | .address" <<<"$json")
  export "$role=$key"
  eval "addr_$role=$addr"  # bash 3.2 (macOS) has no associative arrays
  # 100 fork ETH, except the curator: it starts at 0, as on a fresh testnet, so the deploy
  # must top it up (funding.curator_eth) or the curation transactions fail.
  wei=0x56BC75E2D63100000; [ "$role" = CURATOR_PK ] && wei=0x0
  cast rpc anvil_setBalance "$addr" "$wei" --rpc-url "$node" >/dev/null
done
export "$rpc_env=$node"
# The testnets suggest a 0 priority fee (eth_maxPriorityFeePerGas); Anvil suggests 1 gwei even
# with --no-priority-fee, 100x the testnet base fee, so on the fork each seed actor gets more gas
# money than sim.testnet_eth_per_actor. The curator top-up (funding.curator_eth) is tested as is:
# forge prices its transactions from eth_gasPrice, which the fork keeps near the testnet's.
export AFTERHOURS_SIM__TESTNET_ETH_PER_ACTOR=0.001
export AFTERHOURS_PATHS__DEPLOYMENTS_DIR="$work/deployments"
export AFTERHOURS_PATHS__STATE_DIR="$PWD/$work/state"
$AH deploy
$AH sim seed
$AH bot once
for role in DEPLOYER_PK CURATOR_PK ALLOCATOR_PK GUARDIAN_PK; do
  addr_var="addr_$role"; left=$(cast balance "${!addr_var}" --rpc-url "$node" --ether)
  echo "rehearsal: ${role%_PK} balance now $left ETH"
done
echo "rehearsal: deployment written to $work/deployments/$profile.json"
jq '{profile, chain_id, vault: .vault.address, registry: .registry.address, markets: (.markets | length)}' "$work/deployments/$profile.json"
