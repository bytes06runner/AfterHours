# Contract source verification and roles: Robinhood Chain testnet (chain id 46630)

Checked 2026-10-07 around 17:00 UTC. Verification status comes from the explorer API
(`/api/v2/smart-contracts/<address>` on the explorer in `config/afterhours.yaml`,
`chains.robinhood-testnet.explorer_url`). Addresses come from `deployments/rh-testnet.json`.
Roles, timelocks and balances were read onchain with the engine's `call_many` against the
testnet public RPC.

## Source verification: all 18 deployed contracts are verified

The WAR ROOM, written earlier on 2026-10-07, said the contracts were not verified. The explorer
now shows every one as verified, with `verified_at` between **16:23 and 16:28 UTC on
2026-10-07**. That is before this implementation session changed anything, so this session did
not do it. It was most likely the previous session or a founder. We did not redeploy and did not
re-verify.

All 18 are "partial" matches. That is the strongest match these builds allow:
`contracts/foundry.toml` sets `bytecode_hash = "none"` (as morpho-org/vault-v2 compiles), so the
bytecode carries no metadata hash for the explorer to match fully.

| Role | Address | Contract | Compiler | Match | Verified at (UTC) |
|---|---|---|---|---|---|
| Morpho Blue (self-deployed) | `0xFeE49d53CF7a073b75917F0d9343e7C660C4A06e` | Morpho | 0.8.19 | partial | 2026-10-07 16:28:07 |
| Adaptive Curve IRM | `0x3BC1B8a32ca40320Baf2b1591a393EB6a2C0b6Bc` | AdaptiveCurveIrm | 0.8.19 | partial | 2026-10-07 16:28:03 |
| Vault V2 factory | `0x67522A3108AE6423086eE526616E206cdA58bFF4` | VaultV2Factory | 0.8.28 | partial | 2026-10-07 16:27:58 |
| Adapter factory | `0x20C200D0c33db355DC1a96C50c76FdEB90F327eE` | MorphoMarketV1AdapterV2Factory | 0.8.28 | partial | 2026-10-07 16:28:00 |
| Loan token (Simulation) | `0xd7E9A7FA8eF842fc785309fcF6a2e0F463b8cb6c` | SimUSDG | 0.8.28 | partial | 2026-10-07 16:24:37 |
| **Vault** | `0xD4791630C02FF7462536bAEae7BcE13c5917E6d3` | VaultV2 | 0.8.28 | partial | 2026-10-07 16:25:58 |
| Adapter | `0x3A59C9B5134C9A1Cd6EA75ac8088aa06a6D321E2` | MorphoMarketV1AdapterV2 | 0.8.28 | partial | 2026-10-07 16:28:00 |
| **Reason registry** | `0x2416C56ea86895cf2dE81eBe0Da1f742bDb30ee0` | AfterhoursReasonRegistry | 0.8.28 | partial | 2026-10-07 16:23:13 |
| Collateral META (Simulation) | `0xc7bA7539cB6755add50E218e0e090274dE72472b` | SimStockToken | 0.8.28 | partial | 2026-10-07 16:24:46 |
| Collateral NVDA (Simulation) | `0xC932b9Bd10e7B0A4e5B6Fb8Ed79d45ccA7637954` | SimStockToken | 0.8.28 | partial | 2026-10-07 16:24:44 |
| Collateral SGOV (Simulation) | `0xAEBfc9655B7EA5D136ac52F3F47236127CE1213E` | SimStockToken | 0.8.28 | partial | 2026-10-07 16:24:43 |
| Collateral SPY (Simulation) | `0x29610DC44E46ed1412f424BF2719F24b70cb657d` | SimStockToken | 0.8.28 | partial | 2026-10-07 16:24:37 |
| Collateral USO (Simulation) | `0x896FCc68C2014Ad86b7D7eE8Bb7B46CB3D13B24d` | SimStockToken | 0.8.28 | partial | 2026-10-07 16:24:41 |
| Oracle META (Simulation) | `0x0d0dA945265DEc89573470F35A1Df079ADE6cB7D` | SimOracle | 0.8.28 | partial | 2026-10-07 16:24:48 |
| Oracle NVDA (Simulation) | `0xE9a8a0fC43c7Fed6Ea09f9Fc93332C2ef14C271F` | SimOracle | 0.8.28 | partial | 2026-10-07 16:24:56 |
| Oracle SGOV (Simulation) | `0x191ef0f7599d4A6f25B70d4B520A324ef0586f51` | SimOracle | 0.8.28 | partial | 2026-10-07 16:24:51 |
| Oracle SPY (Simulation) | `0xF094b0124545231d923380803f21bE453121BB92` | SimOracle | 0.8.28 | partial | 2026-10-07 16:24:57 |
| Oracle USO (Simulation) | `0x2937978c2D94253AA8C4150Ab2445aDcFDBF43Da` | SimOracle | 0.8.28 | partial | 2026-10-07 16:24:53 |

Compilers: 0.8.28 is `v0.8.28+commit.7893614a`, EVM cancun. 0.8.19 is `v0.8.19+commit.7dd6d404`,
EVM paris, Morpho's upstream settings. All builds: optimizer on, 100,000 runs, bytecodeHash none.

Re-verifying one contract, if ever needed (Foundry required; it could not be installed in this
cloud session because its installer host is blocked by the egress policy):

```bash
cd contracts
forge verify-contract 0x2416C56ea86895cf2dE81eBe0Da1f742bDb30ee0 \
  src/AfterhoursReasonRegistry.sol:AfterhoursReasonRegistry \
  --chain-id 46630 --verifier blockscout \
  --verifier-url "$(uv run afterhours config get chains.robinhood-testnet.explorer_api_url | tr -d '"')" \
  --compiler-version v0.8.28+commit.7893614a --num-of-optimizations 100000 --via-ir \
  --evm-version cancun --watch
```

Not covered: Arbitrum Sepolia (nothing deployed, BLOCKED 2 in PROGRESS.md) and Robinhood Chain
mainnet (Afterhours has no contract there; the mainnet product is read-only).

## Roles (read onchain)

| Role | Address | Kind | ETH balance | Onchain check |
|---|---|---|---|---|
| Owner (vault and registry) | `0x5006323b641AFBEE80a88BB885af2caa1c0e0E01` | EOA (no code) | 0.00660 | `owner()` on vault and registry |
| Curator | `0x575Eb7f4257f58E9dcB68aB84d592DfFAe926dc4` | EOA | 0.00042 | `curator()` |
| Allocator (bot) | `0x4f9ad36c2cab98A51255d054eB57dbaF48a91c11` | EOA | 0.00199 | `isAllocator()` true; registry `allocator()` |
| Guardian (sentinel) | `0x61d30FC7CF81e36cDfcF4607E3D912BD2B4A74ed` | EOA | **0** | `isSentinel()` true |

No multisig exists on this testnet deployment. The guardian cannot pay gas, so it could not
use its emergency powers today.

## Timelocks on the vault (read onchain, `timelock(bytes4)`; none abdicated)

| Function | Selector | Timelock (s) |
|---|---|---|
| `setIsAllocator` | `0xb192a84a` | 86,400 |
| `addAdapter` | `0x60d54d41` | 86,400 |
| `setPerformanceFee` | `0x70897b23` | 86,400 |
| `increaseAbsoluteCap` | `0xf6f98fd5` | 86,400 |
| `increaseRelativeCap` | `0x2438525b` | 86,400 |
| `setReceiveSharesGate` | `0x2cb19f98` | **0** |
| `setSendSharesGate` | `0xc21ad028` | **0** |
| `setReceiveAssetsGate` | `0x04dbf0ce` | **0** |
| `setSendAssetsGate` | `0x871c979c` | 0 |
| `setAdapterRegistry` | `0x5b34b823` | **0** |
| `removeAdapter` | `0x585cd34b` | 0 |
| `setManagementFee` | `0xfe56e232` | **0** |
| `setPerformanceFeeRecipient` | `0x6a5f1aa2` | **0** |
| `setManagementFeeRecipient` | `0x9faae464` | **0** |
| `setForceDeallocatePenalty` | `0x3e9d2ac7` | **0** |
| `abdicate` | `0xb2e32848` | 0 |
| `increaseTimelock` / `decreaseTimelock` | `0x47966291` / `0x5c1a1a4f` | 0 (decreaseTimelock uses the target function's timelock) |

Why the bold rows matter, from VaultV2's own NatSpec (verified source above): the receive-shares,
send-shares and receive-assets gates "can lock users out of exiting the vault". With a zero
timelock, the curator key alone can close the exit at once. The management fee, fee recipients,
adapter registry and force-deallocate penalty can likewise change depositors' terms without
notice. Gates are all unset today (address zero).

What this changes is in `competitive_analysis/IMPLEMENTATION_RESULT.md` (P1-I). In short: the
change is the `increaseTimelock` calls listed there, signed by the curator. This session did
not sign any transaction.
