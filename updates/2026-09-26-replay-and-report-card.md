# Replaying the worst nights

Afterhours now has all six pages working on live data. The replay page takes the largest real
price gaps in our backtest and runs them through two simulated vaults side by side. On the night
META opened 24.5% below its close in October 2022, a vault that always lends at the 91.5% LLTV tier loses
24,300 USDG of a 2,000,000 USDG vault; Afterhours loses 2,228, and the page shows the reason it
would have written before that close.

The report card says in its first sentence that our LightGBM model did not beat a simpler
volatility baseline, so the baseline ships. The almanac lays out the next two weeks of closed
markets with each stock's forecast against each tier's limit. All pages score 87 or more for
performance and 98 or more for accessibility.
