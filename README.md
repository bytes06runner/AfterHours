# Afterhours

A lending vault for Robinhood Stock Tokens that moves lender money to safer Morpho markets before
the stock market closes into risk, and explains every move onchain.

Work in progress for the Colosseum Crypto World's Fair. Status lives in [PROGRESS.md](PROGRESS.md);
the plan in [docs/SPEC.md](docs/SPEC.md) and [docs/DESIGN.md](docs/DESIGN.md).

## Model status

The LightGBM gap model did not beat the simplest baseline on held-out years, so Afterhours
ships the baseline: EWMA volatility scaled by closed hours, calibrated per segment with conformal
prediction. It is calibrated on 1.23 million held-out closed periods (1.08% of earnings nights
fell below the predicted 1-in-100 bad case). The model stays as future work. Details:
`artifacts/model/report_card.json`.

## Run it

From a clean clone, with no `.env` and no keys (everything runs on a local chain, labelled
Simulation):

```bash
make setup     # uv, pnpm and Foundry dependencies; about 5.5 minutes the first time
make demo      # local chain, contracts, seeded borrowers, API, bot, web app, then the closing bell
```

`make demo` fetches daily prices and earnings for the five vault stocks on its first run, deploys
Morpho, the vault and simulated Stock Tokens on Anvil, and runs the closing-bell scenario: the bot
forecasts the coming closed periods, moves money out of the markets whose cushion is too thin,
and anchors a reason for each move in the onchain registry. It took 1 minute 12 seconds on the
clean-clone check (2026-09-26). Open the web app at `http://localhost:$WEB_PORT` (3000 unless
you change it). Ports come from `.env.example`; set `ANVIL_PORT`, `API_PORT` or `WEB_PORT` in
the environment to use others.

`make up` starts the same stack without the scripted scenario. With it running:

```bash
make e2e          # Playwright: the demo flow, every page on desktop and mobile, error states
make lighthouse   # production build, every page
make screens      # screenshots at 1440, 1024 and 390 px
```

For testnet and mainnet work, `cp .env.example .env` and fill in the RPC URLs. `make help`
lists every command.
