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

```bash
make setup
cp .env.example .env   # then fill it in
make lint test
```

`make help` lists every command.
