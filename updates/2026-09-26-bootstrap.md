# Day one: the skeleton

We set up the Afterhours repo today. There is one config file for every address, threshold and
schedule, checked by a typed loader in Python and another in the web app, and a lint step that
fails the build if an address or URL sneaks into the code. The Python engine, the Next.js app and
the Foundry contracts all build and test with one command.

Nothing user-facing yet. Next we go onchain: finding and verifying the Morpho contracts, USDG and
the Stock Tokens on Robinhood Chain, and answering three questions that shape the design. Do the
Stock Token oracles freeze over the weekend? Can the tokens move into a lending market? Is there a
Morpho vault factory on the chain?
