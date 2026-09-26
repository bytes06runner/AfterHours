# M1 discovery findings

Run: `afterhours discover` at Robinhood Chain block 73,040,830 (2026-09-26 11:17 UTC), public RPC.
Full evidence per address: `deployments/fork.discovered.json`. Independent check:
`make verify-discovered` (plain `cast` calls) passed 81 of 81.

## Sources

| Fact | Source |
| --- | --- |
| Chain ids, RPCs, explorers | https://docs.robinhood.com/chain/connecting, Arbitrum docs (`chain-info`), each checked with `cast chain-id` |
| USDG, WETH | https://docs.robinhood.com/chain/contracts |
| Stock Tokens | https://api.robinhood.com/rhj/assets (195 tokens, all on chain 4663) |
| Chainlink feeds | https://reference-data-directory.vercel.app/feeds-robinhood-mainnet.json (35 equity feeds, `us_equities_24/5`, 8 decimals, 24 h heartbeat, 0.5% deviation) |
| Morpho | Morpho SDK address book (`morpho-org/sdks`, `addresses.ts`), Morpho API for markets and vaults |
| Uniswap | https://developers.uniswap.org/deployments.json (from `Uniswap/contracts`) |

| Chain | Chain id | Explorer |
| --- | --- | --- |
| Robinhood Chain | 4663 | https://robinhoodchain.blockscout.com |
| Robinhood Chain testnet | 46630 | https://explorer.testnet.chain.robinhood.com |
| Arbitrum One | 42161 | https://arbiscan.io |
| Arbitrum Sepolia | 421614 | https://sepolia.arbiscan.io |

## Contracts (Robinhood Chain, all verified)

| Name | Address |
| --- | --- |
| Morpho Blue | `0x9D53d5E3bd5E8d4Cbfa6DB1ca238AEA02E651010` |
| Adaptive Curve IRM | `0x2BD3d5965B26B51814AC95127B2b80dD6CcC0fa1` |
| Morpho Chainlink oracle V2 factory | `0xB7c16F6F8cF531447Bf27Ca7220f981E79C9cdF2` |
| Vault V2 factory | `0x0FBad98595b0186dA120E41f77C102beb49f803c` |
| Market V1 adapter V2 factory | `0x79370Ed003CE325C088E530d5e8655c99c2993e1` |
| USDG | `0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168` |
| WETH | `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73` |
| Uniswap v3 factory, QuoterV2 | `0x1f7d7550B1b028f7571E69A784071F0205FD2EfA`, `0x33e885eD0Ec9bF04EcfB19341582aADCb4c8A9E7` |
| Uniswap v4 PoolManager, StateView, V4Quoter | `0x8366a39CC670B4001A1121B8F6A443A643e40951`, `0xF3334192D15450CdD385c8B70e03f9A6bD9E673b`, `0x8Dc178eFB8111BB0973Dd9d722ebeFF267c98F94` |

Morpho Blue's deployed bytecode contains `LIQUIDATION_CURSOR = 0.3e18`,
`MAX_LIQUIDATION_INCENTIVE_FACTOR = 1.15e18` and `MAX_FEE = 0.25e18`, matching morpho-blue v1.0.0
`ConstantsLib.sol`. The incentive formula in `Morpho.sol` line 365 is
`min(1.15, 1 / (1 - 0.3 * (1 - LLTV)))`, which equals the SPEC's expected form.

Enabled LLTVs (every `EnableLltv` event, each rechecked with `isLltvEnabled`):
0, 38.5%, 62.5%, 77%, 86%, 91.5%, 94.5%, 96.5%, 98%. The allowance is
`b = LLTV * (LIF - 1)` and the cushion is `1 - LLTV - b`: the drop a position sitting at its LLTV
can take before the collateral no longer covers debt plus the incentive.

| LLTV | Incentive factor | b | Cushion |
| --- | --- | --- | --- |
| 38.5% | 1.15 | 5.8% | 55.7% |
| 62.5% | 1.1268 | 7.9% | 29.6% |
| 77% | 1.0741 | 5.7% | 17.3% |
| 86% | 1.0438 | 3.8% | 10.2% |
| 91.5% | 1.0262 | 2.4% | 6.1% |

## Selected Stock Tokens

Rule: a Chainlink feed, then rank by summed Uniswap sell depth at 2% slippage (quoted with the
official QuoterV2 and V4Quoter at $1k to $30M, against the Chainlink price, fees included), keep
depth of at least $250k, top 5.

| Token | Token address | Feed proxy | Depth at 2% | Existing Morpho LLTVs |
| --- | --- | --- | --- | --- |
| NVDA | `0xd0601CE157Db5bdC3162BbaC2a2C8aF5320D9EEC` | `0x379EC4f7C378F34a1B47E4F3cbeBCbAC3E8E9F15` | $2.20M | 38.5, 62.5, 77, 86% |
| SPY | `0x117cc2133c37B721F49dE2A7a74833232B3B4C0C` | `0x319724394D3A0e3669269846abE664Cd621f9f6A` | $1.46M | 62.5, 77, 86% |
| META | `0xc0D6457C16Cc70d6790Dd43521C899C87ce02f35` | `0x7C38C00C30BEe9378381E7B6135d7283356D71b1` | $1.28M | 62.5% |
| SGOV | `0x92FD66527192E3e61d4DDd13322Aa222DE86F9B5` | `0xa0DF4ee0fFf975306345875E3548Fcc519577A11` | $1.20M | 86, 91.5% |
| USO | `0xa30FA36Db767ad9eD3f7a60fC79526fB4d56D344` | `0x75a9c76Ef439e2C7c2E5a34Ab105EcFe3766431c` | $1.08M | 38.5, 62.5% |

Depth was measured on a Saturday, when pools trade but feeds are frozen, so slippage against
the feed includes the weekend drift (USO's pool was 1.3% above its feed). Re-measure at the fork
block once an archive RPC is available.

## The three deciding facts

1. **Weekend oracle behaviour: frozen.** Across the last 8 weekends and all 35 Stock Token feeds
   (6,967 updates in the 8 weekend windows, 12,266 including the 8 weekday overnights used as a control), only five updates landed between Friday 20:00 and Sunday 20:00 New York time, and all five arrived 3 to 105 seconds after 20:00 on Friday: late closing prints of the 24/5 session (two moved the price by 0.5%, SNDK up and AMD down; three were SGOV refreshes). After those, every feed was silent until Sunday 20:00. Feeds do update during
   Robinhood's overnight session (weeknights and Sunday night), so weekday overnights are partly
   priced by the oracle and the weekend is the fully blind window. When feeds restart on Sunday
   night they move by 0.89% on average (203 feed-weekends) and up to 7.75% (USO).
   Evidence: `artifacts/discovery/oracle_study.json`.
2. **Transfer restrictions: none found.** For all 5 selected tokens, a fork test at the chain
   head moves tokens from a real holder to fresh accounts, into an arbitrary contract, and into an
   existing Morpho market as collateral and back (10 of 10 pass,
   `artifacts/discovery/transfer_fork_test.txt`, `contracts/test/fork/StockTokenTransfer.t.sol`).
   Decision: `collateral_mode: native` for the fork.
3. **Vault availability: Vault V2.** Robinhood Chain has Morpho's Vault V2 factory (and no
   MetaMorpho factory). `isVaultV2` is true for all 45 Vault V2 vaults the Morpho API lists on the chain. Decision:
   `vault_kind: vault-v2`, `morpho_source: discovered` on the fork. Neither testnet has Morpho, so
   `rh-testnet` and `arb-sepolia` use `morpho_source: self-deployed`.

## Other findings that change the build

- **The public RPC is not an archive node.** It serves state for only the last few minutes, so
  Anvil cannot fork at the pinned block without an archive RPC (listed under BLOCKED). Logs are
  available for any range. Discovery reads state at a block a few seconds behind the head, per
  step, and treats any RPC error other than a revert as a hard failure.
- **Stock Token lending on Robinhood is early.** The Stock Token/USDG Morpho markets hold little
  and lend almost nothing: 6,115 USDG borrowed in total across them. There are no live rates to
  copy, so backtest rates are labelled assumptions with a sensitivity sweep.
- **Feeds are quiet on calm days.** With a 0.5% deviation threshold and a 24 h heartbeat, SPY's
  feed last updated at 12:03 New York time on Friday 2026-09-25. A 90 minute staleness trigger
  would fire all day, so the trigger now uses the feed heartbeat plus a margin.
- **Vault V2 roles.** owner = owner, curator = curator (timelocked actions), allocator = the
  bot (`setIsAllocator`, allocate and deallocate within caps without a timelock), guardian =
  sentinel (`setIsSentinel`, can deallocate and decrease caps). Timelocks start at 0 and have no
  minimum; we set one day on cap raises and adapter changes.
