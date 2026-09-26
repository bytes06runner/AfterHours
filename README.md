# Afterhours

A lending vault for Robinhood Stock Tokens that moves lender money to safer Morpho markets before
the stock market closes into risk, and explains every move onchain.

Work in progress for the Colosseum Crypto World's Fair. Status lives in [PROGRESS.md](PROGRESS.md);
the plan in [docs/SPEC.md](docs/SPEC.md) and [docs/DESIGN.md](docs/DESIGN.md).

## Run it

```bash
make setup
cp .env.example .env   # then fill it in
make lint test
```

`make help` lists every command.
