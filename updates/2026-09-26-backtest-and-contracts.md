# Safer and better paid than playing it safe

We replayed 2017 to 2026 for NVDA, SPY, META, SGOV and USO with a simulated $2M vault
(historical stock prices, simulated vault; rates and borrower behaviour are stated assumptions).
Lending at a 77% LTV all week earned 6.85% with $7,491 of bad debt. Afterhours, which lends at
91.5% only when its calibrated bad case is small and moves to 77% ahead of risky nights, earned
7.47% with $5,122 of bad debt. It held up under every sensitivity we ran.

One lesson: money already lent out cannot be moved, so pulling liquidity at the closing bell is
too late for an earnings night. Afterhours looks three closes ahead so loans can roll off first.

The contracts are in: a reason registry, and a deploy script that we ran against Robinhood
Chain's real Morpho and Chainlink contracts in a fork test.
