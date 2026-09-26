# Checking our own claims

We got the submission materials ready: a rewritten README, scripts and shot lists for the pitch
and demo videos, and a logo drawn in code like the rest of the app.

Every number in them now comes from one generated file, and a check fails if a document quotes
a number that is not in it. Doing this caught a mistake on our own landing page. We had written
that every Stock Token price feed stops moving over the weekend. The data says 32 of 35 feeds
posted nothing between Friday and Sunday night, and the other three posted five updates between them, all
in the first two minutes. That sentence is now generated from the study instead of written by
hand.
