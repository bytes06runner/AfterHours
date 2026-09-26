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


if __name__ == "__main__":
    app()
