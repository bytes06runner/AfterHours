# The market filled up, so we asked a different question

Ten days ago, Stock Token markets on Morpho had 6,182 USDG borrowed. We measured again on
October 7th: 1,665,217 borrowed against 1,721,781 supplied, 96.7% lent, almost all at 62.5%
loan-to-value. Our vault's pullback moves only money nobody has borrowed, and in markets this
full that is very little.

So we built the view a curator needs before each close: for every live market, tonight's bad
case against the market's cushion, the highest loan-to-value that survives it, how much lenders
could withdraw, and one call (cut the cap, hold it, watch, or survives the modelled bad case).
On the first read nothing breached overnight; the real risk was exit, with four big markets
almost fully lent, two of them completely.

We also fixed what was not true: the scheduled bot had never run in its window, and DEX
prices were silently missing.
