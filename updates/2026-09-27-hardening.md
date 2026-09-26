# Testing the demo like a visitor would

This step was about making Afterhours hold up when someone else runs it. A browser test suite now
walks through the demo as a visitor: it opens every page on a desktop and a phone screen, forces
the closing bell on the simulated chain, waits for the new reason in the ledger and checks its hash
onchain from the browser. It also cuts the API off to make sure each page says what went wrong.

The tests found five real bugs, including pages that crashed when the API was down and an error
message that promised a retry that never happened. All are fixed. From a fresh clone with no
configuration, setup takes about five and a half minutes and the full demo about one minute.
