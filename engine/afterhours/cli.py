"""Typer command line for Afterhours. Subcommands are added per milestone."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from afterhours.config import load_config, write_schema
from afterhours.public_config import public_config

app = typer.Typer(no_args_is_help=True, help="Afterhours engine, bot and tooling.")
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


if __name__ == "__main__":
    app()
