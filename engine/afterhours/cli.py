"""Typer command line for Afterhours. Subcommands are added per milestone."""

from __future__ import annotations

import json
import logging
from typing import Annotated

import typer

from afterhours.config import load_config, write_schema
from afterhours.public_config import public_config

app = typer.Typer(
    no_args_is_help=True, help="Afterhours engine, bot and tooling.", pretty_exceptions_enable=False
)
config_app = typer.Typer(no_args_is_help=True, help="Configuration tools.")
app.add_typer(config_app, name="config")


@config_app.command("schema")
def config_schema() -> None:
    """Regenerate config/schema.json from the pydantic model."""
    typer.echo(f"wrote {write_schema()}")


@config_app.command("check")
def config_check() -> None:
    """Load and validate the configuration, then print the active profile."""
    cfg = load_config()
    typer.echo(f"ok: profile={cfg.active_profile} chain={cfg.profile.chain}")


@config_app.command("get")
def config_get(key: Annotated[str, typer.Argument(help="Dotted path, e.g. vault.symbol")]) -> None:
    """Print one config value as JSON."""
    node: object = load_config().model_dump(mode="json")
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise typer.BadParameter(f"unknown key {key}")
        node = node[part]
    typer.echo(json.dumps(node))


@config_app.command("public")
def config_public() -> None:
    """Print the public config document served to the web app."""
    typer.echo(json.dumps(public_config(load_config()), indent=2))


@app.command("discover")
def discover_cmd(
    oracle_study: Annotated[bool, typer.Option(help="Run the weekend oracle study.")] = True,
) -> None:
    """M1: find protocol addresses in primary sources, verify onchain, write evidence."""
    from afterhours.discovery.run import discover, write

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    result = discover(cfg, run_oracle_study=oracle_study)
    for path in write(cfg, result):
        typer.echo(f"wrote {path}")
    doc = result["discovered"]
    typer.echo(f"selected: {', '.join(doc['selected']) or 'none'}")
    typer.echo(f"failures: {len(doc['_failures'])}")


data_app = typer.Typer(no_args_is_help=True, help="Market data and the gap dataset.")
app.add_typer(data_app, name="data")


@data_app.command("build")
def data_build() -> None:
    """M2: fetch prices and earnings (cached) and build the gap dataset."""
    from afterhours.data.pipeline import build

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    _, manifest = build(load_config())
    typer.echo(json.dumps(manifest, indent=2))


@data_app.command("fetch")
def data_fetch(symbols: Annotated[list[str] | None, typer.Argument()] = None) -> None:
    """Prices and earnings for the vault's stocks only (enough for the bot, API and demo)."""
    from afterhours.data.pipeline import fetch_symbols, vault_symbols

    rows = fetch_symbols(load_config(), symbols or vault_symbols(load_config()))
    typer.echo(json.dumps(rows))


@app.command("gaps")
def gaps_cmd() -> None:
    """M2: write the gap study (artifacts/gaps) from the cached dataset."""
    from afterhours.data.pipeline import DATASET_KEY, make_cache
    from afterhours.data.universe import stock_token_tickers
    from afterhours.features import gaps

    cfg = load_config()
    cache = make_cache(cfg)
    data = cache.get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    tokens, selected = stock_token_tickers(cfg)
    manifest = cache.entry(DATASET_KEY) or {}
    doc = gaps.study(
        data,
        selected=selected,
        stock_tokens=tokens,
        quantiles=cfg.gaps.quantiles,
        drops=cfg.gaps.drop_thresholds,
        worst_n=cfg.gaps.worst_n,
        data_manifest=manifest,
    )
    out = cfg.path(cfg.paths.artifacts_dir) / "gaps"
    typer.echo(f"wrote {gaps.write_summary(doc, out)}")
    for path in gaps.figures(data, selected, out):
        typer.echo(f"wrote {path}")


@app.command("model")
def model_cmd() -> None:
    """M3: walk-forward evaluation, acceptance, report card and the production model."""
    from afterhours.data.pipeline import DATASET_KEY, make_cache
    from afterhours.model.report import build_report

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    cache = make_cache(cfg)
    data = cache.get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    card = build_report(cfg, data, cache.entry(DATASET_KEY) or {})
    typer.echo(card["first_sentence"])
    typer.echo(
        json.dumps(
            {
                k: card["acceptance"][k]
                for k in (
                    "coverage_overall",
                    "coverage_earnings",
                    "pinball_vs_baselines",
                    "shipped",
                )
            },
            indent=2,
        )
    )


@app.command("backtest")
def backtest_cmd() -> None:
    """M4: four strategies, tuning sweep, sensitivity and replay scenarios."""
    from afterhours.backtest.run import load_inputs, run
    from afterhours.data.pipeline import DATASET_KEY, make_cache
    from afterhours.data.universe import stock_token_tickers

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    cfg = load_config()
    cache = make_cache(cfg)
    data = cache.get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    heldout, card = load_inputs(cfg)
    _, selected = stock_token_tickers(cfg)
    prices = {t: cache.get(f"prices/{t}", allow_stale=True) for t in selected}
    res = run(
        cfg, data, heldout, card, {t: f for t, f in prices.items() if f is not None}, selected
    )
    typer.echo(
        json.dumps(
            {
                "chosen": res["chosen"],
                "strategies": {
                    k: {
                        m: v[m]
                        for m in ("net_lender_yield_annualised", "bad_debt_usdg", "bad_debt_events")
                    }
                    for k, v in res["strategies"].items()
                },
            },
            indent=2,
        )
    )


@app.command("deploy")
def deploy_cmd(
    plan_only: Annotated[bool, typer.Option(help="Write the plan file and stop.")] = False,
) -> None:
    """M5: deploy markets, vault, adapter and registry for the active profile."""
    from afterhours import deploy as dep
    from afterhours.deployments import deployment_path

    cfg = load_config()
    profile = cfg.active_profile
    if cfg.profile.requires_human_go:
        raise typer.BadParameter(f"{profile} needs an explicit human go in PROGRESS.md first")
    plan_doc = dep.plan(cfg, profile)
    plan_path = deployment_path(cfg, profile).with_suffix(".plan.json")
    plan_path.write_text(json.dumps(plan_doc, indent=2) + "\n")
    if plan_only:
        typer.echo(f"wrote {plan_path}")
        return
    rpc = cfg.node_url(profile)
    keys = dep.role_keys(cfg, profile)
    if cfg.profile.local_rpc_port_env:
        dep.fund_local(rpc, list(dep.addresses(keys).values()), 1000 * 10**18)
    raw_path = deployment_path(cfg, profile).with_suffix(".raw.json")
    dep.run_script(cfg, profile, plan_path, raw_path, rpc, keys)
    doc = dep.finalise(cfg, profile, raw_path, plan_doc)
    typer.echo(
        f"deployed {profile}: vault {doc['vault']['address']}, {len(doc['markets'])} markets"
    )


bot_app = typer.Typer(no_args_is_help=True, help="Allocator bot.")
app.add_typer(bot_app, name="bot")
sim_app = typer.Typer(no_args_is_help=True, help="Simulation harness (fork and local chains only).")
app.add_typer(sim_app, name="sim")


def _logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


@bot_app.command("once")
def bot_once(
    trigger: Annotated[str, typer.Option(help="Label recorded with the cycle.")] = "manual",
    dry_run: Annotated[bool, typer.Option(help="Plan without sending transactions.")] = False,
) -> None:
    """Run one planning cycle now."""
    from afterhours.bot.allocator import Allocator, dump

    _logging()
    typer.echo(dump(Allocator(load_config()).run_cycle(trigger, execute=not dry_run)))


@bot_app.command("run")
def bot_run() -> None:
    """Run the scheduler: hourly, pre-close, post-open, pre-earnings and trigger cycles."""
    from afterhours.bot.scheduler import BotScheduler

    _logging()
    BotScheduler(load_config()).run()


@sim_app.command("seed")
def sim_seed() -> None:
    """Seed lenders, let the bot allocate, then seed borrowers."""
    from afterhours.bot.allocator import Allocator
    from afterhours.chain.rpc import connect
    from afterhours.deployments import load_deployment
    from afterhours.sim.seed import Seeder

    _logging()
    cfg = load_config()
    if not cfg.profile.local_rpc_port_env and cfg.profile.collateral_mode != "simulated":
        raise typer.BadParameter("seeding needs Anvil or simulated tokens (testnet profiles)")
    if cfg.profile.requires_human_go:
        raise typer.BadParameter(f"{cfg.active_profile} needs an explicit human go first")
    seeder = Seeder(cfg, connect(cfg.node_url()), load_deployment(cfg))
    lenders = seeder.lenders()
    typer.echo(f"lenders: {len(lenders)}, {sum(x['usdg'] for x in lenders):,.0f} USDG")
    Allocator(cfg).run_cycle("seed")
    borrowers = seeder.borrowers()
    typer.echo(
        f"borrowers: {len(borrowers)}, {sum(x['usdg'] for x in borrowers):,.0f} USDG borrowed"
    )


@app.command("numbers")
def numbers_cmd() -> None:
    """M12: write artifacts/report/numbers.json, the numbers the README and pitch quote."""
    from afterhours.numbers import write

    typer.echo(f"wrote {write(load_config())}")


@app.command("api")
def api_cmd() -> None:
    """Start the FastAPI service (host and port from the env vars named in config)."""
    from afterhours.api.app import serve

    serve()


@sim_app.command("scenario")
def sim_scenario(
    name: Annotated[str, typer.Argument(help="closing_bell | earnings_shock | oracle_drift")],
) -> None:
    """Run one scripted scenario (Simulation)."""
    from afterhours.sim import scenarios

    _logging()
    cfg = load_config()
    if not cfg.profile.local_rpc_port_env:
        raise typer.BadParameter("scenarios run only on fork and local chains")
    d = cfg.demo
    if name == "closing_bell":
        out = scenarios.closing_bell(cfg, d.max_closes)
    elif name == "earnings_shock":
        out = scenarios.earnings_shock(cfg, d.earnings_shock.symbol, d.earnings_shock.pct)
    elif name == "oracle_drift":
        o = d.oracle_drift
        out = scenarios.oracle_drift(cfg, o.symbol, o.step_pct, o.steps, o.minutes_per_step)
    else:
        raise typer.BadParameter(f"unknown scenario {name}")
    typer.echo(json.dumps(out, indent=2, default=str))


@app.command("replay")
def replay_cmd() -> None:
    """Regenerate replay scenarios with the settings chosen by the last backtest."""
    from afterhours.backtest.run import load_inputs, write_replays
    from afterhours.data.pipeline import DATASET_KEY, make_cache
    from afterhours.data.universe import stock_token_tickers

    _logging()
    cfg = load_config()
    cache = make_cache(cfg)
    data = cache.get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    heldout, card = load_inputs(cfg)
    _, selected = stock_token_tickers(cfg)
    prices = {t: cache.get(f"prices/{t}", allow_stale=True) for t in selected}
    for path in write_replays(
        cfg, data, heldout, card, {t: f for t, f in prices.items() if f is not None}, selected
    ):
        typer.echo(f"wrote {path}")


if __name__ == "__main__":
    app()
