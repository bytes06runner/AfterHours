"""Typer command line for Afterhours. Subcommands are added per milestone."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
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
def data_fetch(
    symbols: Annotated[list[str] | None, typer.Argument()] = None,
    stock_tokens: Annotated[
        bool, typer.Option(help="Every Stock Token with a feed (the risk board and alerts).")
    ] = False,
) -> None:
    """Prices and earnings for the vault's stocks only (enough for the bot, API and demo)."""
    from afterhours.data.pipeline import fetch_symbols, vault_symbols
    from afterhours.data.universe import stock_token_tickers

    cfg = load_config()
    live = cfg.live.discovery_profile
    wanted = symbols or (stock_token_tickers(cfg, live)[0] if stock_tokens else vault_symbols(cfg))
    typer.echo(json.dumps(fetch_symbols(cfg, wanted)))


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
    else:
        sent = dep.top_up_curator(cfg, rpc, keys)
        typer.echo(f"curator topped up by {sent / 1e18:.6f} ETH" if sent else "curator has gas")
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


@bot_app.command("due")
def bot_due() -> None:
    """One pre-close cycle per close, only inside the pre-close window (for scheduled jobs)."""
    from afterhours.bot.allocator import Allocator, dump
    from afterhours.bot.scheduler import pre_close_window
    from afterhours.deployments import deployment_path
    from afterhours.state import Store

    _logging()
    cfg = load_config()
    close = pre_close_window(cfg, datetime.now(UTC))
    if close is None:
        typer.echo("not in a pre-close window; nothing to do")
        return
    if not deployment_path(cfg).exists():
        typer.echo(f"no deployment for {cfg.active_profile} yet; nothing to do")
        return
    store = Store.for_profile(cfg)
    done = store.read("pre_close_run")
    if done and done.get("close") == close.isoformat():
        typer.echo(f"already ran for the {close.isoformat()} close")
        return
    typer.echo(dump(Allocator(cfg).run_cycle("pre_close")))
    store.write("pre_close_run", {"close": close.isoformat(), "at": datetime.now(UTC).isoformat()})


@app.command("pre-close")
def pre_close_cmd() -> None:
    """Print `true` inside a pre-close window, else `false` (scheduled jobs gate on it)."""
    from afterhours.bot.scheduler import pre_close_window

    typer.echo("true" if pre_close_window(load_config(), datetime.now(UTC)) else "false")


@bot_app.command("run")
def bot_run() -> None:
    """Run the scheduler: hourly, pre-close, post-open, pre-earnings and trigger cycles."""
    from afterhours.bot.scheduler import BotScheduler

    _logging()
    BotScheduler(load_config()).run()


@app.command("testnet-keys")
def testnet_keys_cmd() -> None:
    """Make the four testnet keys with `cast wallet new` and write them into .env.

    Prints roles and addresses only, never a key. Refuses if any role already has a key.
    """
    from afterhours.deploy import write_testnet_keys

    cfg = load_config(load_env_file=False)
    env_path = cfg.path(cfg.paths.env_file)
    try:
        who = write_testnet_keys(env_path)
    except KeyError as exc:
        raise typer.BadParameter(str(exc.args[0])) from None
    typer.echo(f"Wrote 4 new testnet keys to {env_path.name} (not shown). Addresses:")
    for role, address in who.items():
        typer.echo(f"  {role.removesuffix('_PK').lower():<10} {address}")
    prof = cfg.profiles[cfg.funding.faucet_profile]
    chain = cfg.chains[prof.chain]
    typer.echo(f"\nNext: fund the deployer on {chain.name} (docs/HOSTING.md step 9).")
    typer.echo(f"Faucet:           {chain.faucet_url}")
    typer.echo(f"Deployer address: {who['DEPLOYER_PK']}")


@app.command("fund-allocator")
def fund_allocator_cmd(
    profile: Annotated[str, typer.Option(help="A testnet profile: rh-testnet or arb-sepolia.")],
    yes: Annotated[bool, typer.Option("--yes", help="Send without asking.")] = False,
) -> None:
    """Send testnet ETH from the deployer to the allocator (keys from .env, never printed)."""
    from eth_utils.address import to_checksum_address

    from afterhours.chain.rpc import connect
    from afterhours.chain.tx import Signer
    from afterhours.deploy import addresses, role_keys

    cfg = load_config()
    prof = cfg.profiles.get(profile)
    chain = cfg.chains[prof.chain] if prof else None
    # Testnets only: a chain with a faucet, no local node, no mainnet go required.
    testnet = bool(chain and chain.faucet_url) and not (
        prof is None or prof.requires_human_go or prof.local_rpc_port_env
    )
    if not prof or not chain or not testnet:
        raise typer.BadParameter(f"{profile} is not a testnet profile with a faucet")
    keys = role_keys(cfg, profile, ("DEPLOYER_PK", "ALLOCATOR_PK"))
    who = addresses(keys)
    w3 = connect(cfg.rpc_url(profile))

    def balance(role: str) -> int:
        return int(w3.eth.get_balance(to_checksum_address(who[role])))

    if chain.chain_id and int(w3.eth.chain_id) != chain.chain_id:
        raise typer.BadParameter(f"RPC answers chain {w3.eth.chain_id}, expected {chain.chain_id}")
    unit = chain.native_currency.symbol
    amount = int(cfg.funding.allocator_eth * 10**18)
    keep = int(cfg.funding.keep_deployer_eth * 10**18)
    have = balance("DEPLOYER_PK")
    typer.echo(f"{chain.name}: deployer {who['DEPLOYER_PK']} has {have / 1e18:.6f} {unit}")
    typer.echo(f"allocator {who['ALLOCATOR_PK']} has {balance('ALLOCATOR_PK') / 1e18:.6f} {unit}")
    if have < amount + keep:
        raise typer.BadParameter(
            f"the deployer needs at least {(amount + keep) / 1e18} {unit}: "
            f"fund it at {chain.faucet_url}"
        )
    if not yes and not typer.confirm(f"Send {amount / 1e18} {unit} to the allocator?"):
        raise typer.Exit(1)
    sent = Signer(w3, keys["DEPLOYER_PK"]).transfer(who["ALLOCATOR_PK"], amount)
    link = f"{chain.explorer_url}/tx/{sent.tx_hash}" if chain.explorer_url else sent.tx_hash
    typer.echo(f"sent: {link}")
    typer.echo(f"allocator now has {balance('ALLOCATOR_PK') / 1e18:.6f} {unit}")


state_app = typer.Typer(no_args_is_help=True, help="Bot history storage.")
app.add_typer(state_app, name="state")


@state_app.command("copy-to-shared")
def state_copy_to_shared(
    profile: Annotated[str, typer.Option(help="Whose history to copy, e.g. rh-testnet.")],
    dry_run: Annotated[
        bool, typer.Option(help="Count what would be copied; write nothing.")
    ] = False,
) -> None:
    """One-time: copy a profile's local bot history (events, reason cards, plan) into Upstash."""
    from afterhours.kv import kv_from_config
    from afterhours.state import KVStore, Store, copy_to_shared

    cfg = load_config()
    kv = kv_from_config(cfg)
    if kv is None:
        raise typer.BadParameter(
            f"set {cfg.state.kv_url_env} and {cfg.state.kv_token_env} in .env first"
        )
    root = cfg.path(cfg.paths.state_dir) / profile
    if not root.is_dir():
        raise typer.BadParameter(f"no local history for {profile} at {root}")
    try:
        n = copy_to_shared(Store(root), KVStore(kv, profile, cfg), dry_run=dry_run)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    verb = "would copy" if dry_run else "copied"
    typer.echo(
        f"{verb} {n['events']} events, {n['reasons']} reason cards and "
        f"{n['documents']} documents for {profile}"
    )


alerts_app = typer.Typer(no_args_is_help=True, help="Telegram alerts (read-only, mainnet).")
app.add_typer(alerts_app, name="alerts")


@alerts_app.command("check")
def alerts_check() -> None:
    """Send what is due before this close, once (for scheduled jobs); else do nothing."""
    from afterhours.live.alerts import AlertBot, telegram_from_config
    from afterhours.live.mainnet import Mainnet

    _logging()
    cfg = load_config()
    if not cfg.env(cfg.alerts.token_env):
        # Not set up yet (docs/HOSTING.md step 8): skip without failing the scheduled run.
        typer.echo(f"{cfg.alerts.token_env} is not set; no alerts to send")
        return
    sent = AlertBot(cfg, Mainnet(cfg), telegram_from_config(cfg)).check()
    typer.echo(f"sent {sent} alerts")


@alerts_app.command("set-webhook")
def alerts_set_webhook(
    api_url: Annotated[str, typer.Argument(help="The API's public URL, e.g. your Render URL.")],
) -> None:
    """Point Telegram at the API's webhook (uses the token and webhook secret from .env)."""
    from urllib.parse import urlparse

    from afterhours.live.alerts import telegram_from_config

    cfg = load_config()
    secret = cfg.env(cfg.alerts.webhook_secret_env)
    if not secret:
        raise typer.BadParameter(f"set {cfg.alerts.webhook_secret_env} in .env first")
    if urlparse(api_url).scheme != "https":
        raise typer.BadParameter("Telegram only sends webhooks to https URLs")
    tg = telegram_from_config(cfg)
    tg.set_webhook(api_url.rstrip("/") + cfg.alerts.webhook_path, secret)
    info = tg.webhook_info()
    typer.echo(
        f"webhook set: {info.get('url')} (pending updates: {info.get('pending_update_count')})"
    )


@alerts_app.command("delete-webhook")
def alerts_delete_webhook() -> None:
    """Stop the webhook so `alerts run` (long polling) can receive updates again."""
    from afterhours.live.alerts import telegram_from_config

    telegram_from_config(load_config()).delete_webhook()
    typer.echo("webhook removed")


@alerts_app.command("run")
def alerts_run() -> None:
    """Answer Telegram commands and send pre-close alerts. Needs the bot token in .env."""
    from afterhours.data.pipeline import fetch_symbols
    from afterhours.data.universe import stock_token_tickers
    from afterhours.live.alerts import AlertBot, telegram_from_config
    from afterhours.live.mainnet import Mainnet

    _logging()
    cfg = load_config()
    try:
        chat = telegram_from_config(cfg)
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from None

    def refresh() -> None:
        if cfg.alerts.refresh_prices:
            fetch_symbols(cfg, stock_token_tickers(cfg, cfg.live.discovery_profile)[0])

    AlertBot(cfg, Mainnet(cfg), chat, refresh=refresh).run()


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


@app.command("oracle-reading")
def oracle_reading_cmd() -> None:
    """A new dated reading of the weekend oracle study (the M1 reading is never rewritten)."""
    from afterhours.discovery import oracle_readings

    _logging()
    cfg = load_config()
    reading = oracle_readings.take(cfg)
    if reading is None:
        typer.echo(f"no weekend has ended since {oracle_readings.last_covered(cfg).isoformat()}")
        oracle_readings.write_index(cfg)
        return
    path = oracle_readings.write(cfg, reading)
    s = reading["summary"]
    typer.echo(
        f"{s['weekends']} weekend(s) from {s['first_weekend_close']}: {s['feeds_without_update']} "
        f"of {s['feeds']} feeds posted nothing inside the window; "
        f"posted: {', '.join(s['feeds_with_update']) or 'none'} ({s['updates_in_window']} updates)"
    )
    typer.echo(f"wrote {path}")


@app.command("market-size")
def market_size_cmd() -> None:
    """Supplied and borrowed across Stock Token Morpho markets on mainnet, at a recent block."""
    from afterhours.discovery.market_size import read

    _logging()
    cfg = load_config()
    doc = read(cfg)
    out = cfg.path(cfg.paths.artifacts_dir) / "discovery" / "market_size.json"
    out.write_text(json.dumps(doc, indent=2) + "\n")
    u = doc["usdg_loan"]
    typer.echo(
        f"block {doc['block']} ({doc['block_time']}): {doc['stock_token_markets']} Stock Token "
        f"markets ({doc['stock_token_markets_in_morpho_api_at_discovery']} in the API at M1); "
        f"USDG supplied {u['supplied']:,.0f}, borrowed {u['borrowed']:,.0f}"
    )
    typer.echo(f"wrote {out}")


@app.command("option-a")
def option_a_cmd(
    jobs: Annotated[int, typer.Option(help="Worker processes (0: all cores but one)")] = 0,
) -> None:
    """Option A: tune on the tuning years, evaluate once on the held-out years (PROGRESS.md)."""
    from afterhours.backtest.option_a import write
    from afterhours.data.pipeline import DATASET_KEY, make_cache

    _logging()
    cfg = load_config()
    data = make_cache(cfg).get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    typer.echo(f"wrote {write(cfg, data, jobs)}")


@app.command("option-b")
def option_b_cmd(
    jobs: Annotated[int, typer.Option(help="Worker processes (0: all cores but one)")] = 0,
) -> None:
    """Option B: fixed map plus pullback, tuned then evaluated once (PROGRESS.md)."""
    from afterhours.backtest.option_b import write
    from afterhours.data.pipeline import DATASET_KEY, make_cache

    _logging()
    cfg = load_config()
    data = make_cache(cfg).get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    typer.echo(f"wrote {write(cfg, data, jobs)}")


@app.command("b-activity")
def b_activity_cmd() -> None:
    """Measure how often option B pulled money on the held-out years (no strategy change)."""
    from afterhours.backtest.b_activity import write
    from afterhours.data.pipeline import DATASET_KEY, make_cache

    _logging()
    cfg = load_config()
    data = make_cache(cfg).get(DATASET_KEY, allow_stale=True)
    if data is None:
        raise typer.BadParameter("no dataset; run `afterhours data build` first")
    typer.echo(f"wrote {write(cfg, data)}")


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
