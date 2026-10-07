# Stock Token lending on Morpho, Robinhood Chain mainnet: measured 2026-10-07

Measured by us, with the project's own tool, from this repository. Read-only.

- Command: `RH_MAINNET_RPC_URL= uv run afterhours market-size --snapshot` (empty
  `RH_MAINNET_RPC_URL` forces the chain's public RPC from `config/afterhours.yaml`; no API key used)
- Chain: Robinhood Chain mainnet, chain id 4663
- Block: **82,622,425**, block time **2026-10-07 16:43:38 UTC** (30 blocks behind the head)
- Artifact: `artifacts/report/market_snapshot_82622425.json` (every market with its id, params,
  supplied, borrowed, utilization and IRM rates); summary in `artifacts/report/numbers.json`
  under `market_now.*`
- Method (unchanged from the 2026-09-27 measurement, `engine/afterhours/discovery/market_size.py`):
  every `CreateMarket` event of Morpho Blue (0x9D53...1010) from block 0; markets whose
  collateral is one of the 35 discovered Stock Tokens; `market(id)` totals at the block; borrow
  rate from each market's IRM `borrowRateView` at the block. Stored totals: interest accrued
  since each market's last update is not included.
- Runtime: 27 s. One run, not repeated.

## Result

| | 2026-09-27 (block 73,650,323) | **2026-10-07 (block 82,622,425)** |
|---|---|---|
| Stock Token markets (any loan token) | 150 | 151 |
| USDG-loan markets | 148 | 149 |
| USDG supplied | 804,926 | **1,721,781** |
| USDG borrowed | 6,182 | **1,665,217** |
| Utilization | 0.77% | **96.7%** |
| Markets with borrowing | 31 | 34 |
| Borrow APY (borrow-weighted) | 0.20% | **15.9%** |
| Supply APY (supply-weighted) | 0.0016% | **15.4%** |

By LLTV (USDG markets):

| LLTV | Markets | Supplied | Borrowed | Utilization |
|---|---|---|---|---|
| 38.5% | 4 | 329 | 6 | 2.0% |
| **62.5%** | 48 | **1,721,290** | **1,665,197** | **96.7%** |
| 77% | 4 | 50 | 14 | 27.2% |
| 86% | 8 | 111 | 0.08 | 0.1% |
| 91.5% | 1 | 0.000002 | 0 | 0% |

62.5% LLTV markets hold 99.97% of supply.

Largest markets by borrowing:

| Stock | LLTV | Market id | Supplied | Borrowed | Utilization | Exit liquidity (supplied minus borrowed) | Borrow APY |
|---|---|---|---|---|---|---|---|
| NVDA | 62.5% | `0x8b16891f…` | 711,483 | 686,483 | 96.5% | 25,000 | 17.1% |
| SPCX | 62.5% | `0x9b4b47cd…` | 525,862 | 515,862 | 98.1% | 10,000 | 15.3% |
| GOOGL | 62.5% | `0x7fa81b10…` | 259,785 | 259,785 | 100.0% | 0 | 14.7% |
| AAPL | 62.5% | `0xdeb4782d…` | 197,408 | 197,408 | 100.0% | 0 | 15.0% |
| SPY | 62.5% | `0x50bc39b5…` | 11,229 | 5,328 | 47.4% | 5,901 | 0.1% |

The top four markets (NVDA, SPCX, GOOGL, AAPL) carry 99.7% of all USDG borrowed. Four markets
are fully lent (GOOGL, AAPL, MSFT and COIN, the last two tiny): a lender there cannot withdraw
until a borrower repays.

## Compared with the WAR ROOM's figures

The WAR ROOM quoted "about $1.66M borrowed at about 98% utilization, almost all at 62.5% LLTV"
from third-party sources and marked it UNVERIFIED. Our measurement confirms the borrowed amount
(1,665,217 USDG) and the 62.5% concentration. Utilization is 96.7% across all USDG markets
(98.1% in SPCX, 100% in GOOGL and AAPL), not 98% overall.

## What this changes in our story

- "6,182 borrowed, 0.77% utilization" and "0.0016% supply APY" are 10 days old and wrong today.
  They stay true only as dated history (block 73,650,323).
- The market is now almost fully lent at 62.5% LLTV. Afterhours' vault action (pull
  unborrowed money) applies to a few percent of supply in these markets. The decision that
  matters to these lenders is which LLTV survives tonight's modelled bad case, and when to stop
  adding supply or cut caps: the curator view.
- Backtest yields (7.0% to 9.5%, modelled) are now below the live borrow-weighted rate (15.9%).
  The backtest is unchanged (frozen); its rates remain labelled assumptions.

## Not measured here

- Who supplies these markets (which vault or curator). The WAR ROOM's "NetNet Credit" remains
  an UNVERIFIED CLAIM.
- Borrower concentration per market: the curator view (`/v1/live/curator`) reports it from
  `Borrow` events and Morpho `position()`; see `competitive_analysis/IMPLEMENTATION_RESULT.md`.
