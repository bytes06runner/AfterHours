# What the chain told us

We checked every contract we plan to use on Robinhood Chain against its source and onchain:
Morpho, the Vault V2 factory, USDG, Uniswap, and 35 Stock Tokens with Chainlink feeds. An
independent script re-checks all of it with plain cast calls (81 of 81 pass).

The finding that matters most: over the last 8 weekends, Stock Token price feeds stopped moving
at 20:00 New York time on Friday and did not move again until Sunday evening. When they restart
they jump, by up to 7.75% in our sample. The tokens keep trading in the meantime. This Saturday,
one pool was trading 1.3% above its frozen feed.

We also confirmed Stock Tokens move freely into Morpho as collateral, and that Stock Token
lending on Robinhood Chain is still tiny today.
