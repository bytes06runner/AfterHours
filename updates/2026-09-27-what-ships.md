# Testing our own design, and shipping the one that passed

Before submitting, we checked whether Afterhours' nightly moves beat a simple fixed plan. We
wrote the test down first: tune on 2017 to 2021, test once on 2022 to 2026, and the nightly
design only ships if it loses less money than a fixed plan while earning at least as much.

It lost less but earned less, so it did not ship. What ships instead is simpler: each stock
lends in the riskiest market its last year of prices allows, and before a night that could gap
past every market, the money borrowers are not using comes out. On the test years it earned
the same as the best fixed mix with about half the loss. The report card shows all of it,
including where our worst-night target was missed.
