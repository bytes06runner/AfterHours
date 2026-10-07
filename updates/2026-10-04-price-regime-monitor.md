# Frozen today, thin tomorrow: a price regime monitor

Robinhood announced weekend trading for a curated list of stocks and ETFs, pending regulatory
review. Today, Stock Token feeds on Robinhood Chain post nothing from Friday night to Sunday
night; we read one more weekend and it was the same (34 of 35 silent). If the feeds start
following a weekend venue, the risk changes from no price to a thin one.

So Afterhours now classifies every Stock Token, at every refresh, as regular session, extended
hours, weekend price or frozen, and scores how far its price can be trusted: feed staleness
against its normal pace, DEX drift from the feed, and sellable depth. On Sunday, October 4th,
all 35 were frozen; two DEX pools sat 3.4% and 7.3% from their feeds, but with $50 and $73 of
depth, so thin they score as poor.

It is on the landing page and the risk board, and the formula is in docs/REGIME.md. It does not
change the vault's strategy.
