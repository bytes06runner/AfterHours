"""Typed configuration loader for the Afterhours engine, bot and API.

`config/afterhours.yaml` is validated twice: first against `config/schema.json` (a JSON Schema
generated from the models below, so other tools and editors can use it), then by pydantic.
Environment variables prefixed with `AFTERHOURS_` override YAML values, using `__` to reach
nested keys, e.g. `AFTERHOURS_ACTIVE_PROFILE=arb-sepolia` or `AFTERHOURS_VAULT__SYMBOL=x`.

Secrets are never stored here. Fields ending in `_env` hold the *name* of an environment
variable; resolve them with `AfterhoursConfig.env`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal

import jsonschema
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

CONFIG_PATH_ENV = "AFTERHOURS_CONFIG"
"""Environment variable that can point the loader at a different YAML file."""

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "afterhours.yaml"
SCHEMA_PATH = REPO_ROOT / "config" / "schema.json"

HttpUrlStr = Annotated[str, StringConstraints(pattern=r"^https?://")]
EnvName = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]
Fraction = Annotated[float, Field(ge=0, le=1)]
PositiveInt = Annotated[int, Field(gt=0)]
PositiveFloat = Annotated[float, Field(gt=0)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PathsConfig(_Strict):
    artifacts_dir: str
    deployments_dir: str
    env_file: str
    state_dir: str


class LocalNodeConfig(_Strict):
    url_template: Annotated[str, StringConstraints(pattern=r"^https?://.*\{port\}")]
    port_env: EnvName


class ProfileConfig(_Strict):
    chain: str
    rpc_env: EnvName
    fork_block: PositiveInt | None = None
    local_rpc_port_env: EnvName | None = None
    oracle_mode: Literal["chainlink", "simulated"]
    collateral_mode: Literal["native", "simulated"]
    morpho_source: Literal["discovered", "self-deployed"]
    requires_human_go: bool = False


class NativeCurrency(_Strict):
    name: str
    symbol: str
    decimals: PositiveInt


class ChainConfig(_Strict):
    chain_id: PositiveInt | None = None
    name: str
    native_currency: NativeCurrency
    public_rpc_url: HttpUrlStr | None = None
    explorer_url: HttpUrlStr | None = None
    explorer_api_url: HttpUrlStr | None = None
    faucet_url: HttpUrlStr | None = None


class LltvTiers(_Strict):
    weekday: Fraction | None = None
    middle: Fraction | None = None
    weekend: Fraction | None = None

    def ordered(self) -> list[tuple[str, float]]:
        """Configured tiers, highest LLTV first."""
        tiers = [
            (n, v)
            for n, v in (
                ("weekday", self.weekday),
                ("middle", self.middle),
                ("weekend", self.weekend),
            )
            if v is not None
        ]
        return sorted(tiers, key=lambda x: -x[1])


class LiquidationIncentiveConfig(_Strict):
    verify_from: str


class MorphoConfig(_Strict):
    vault_kind: Literal["metamorpho", "vault-v2"] | None = None
    lltv_tiers: LltvTiers
    liquidation_incentive: LiquidationIncentiveConfig


class VaultConfig(_Strict):
    name: str
    symbol: str
    performance_fee_bps: Annotated[int, Field(ge=0, le=10_000)]
    timelock_seconds: Annotated[int, Field(ge=0)] | None = None
    max_share_per_stock: Fraction
    depth_multiplier: Annotated[float, Field(gt=0)]
    max_slippage: Fraction
    market_cap_usdg: Annotated[float, Field(gt=0)]


class OnchainSelection(_Strict):
    max_tokens: PositiveInt
    min_pool_depth_usd: Annotated[float, Field(ge=0)]


class UniverseConfig(_Strict):
    onchain_selection: OnchainSelection
    training_universe_source: Literal["sp500", "explicit"]
    training_universe_url_env: EnvName | None = None
    explicit_tickers: list[str] = Field(default_factory=list)
    history_start: Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class DataSources(_Strict):
    sp500_constituents_url: HttpUrlStr
    stooq_daily_url: HttpUrlStr
    alphavantage_url: HttpUrlStr
    finnhub_url: HttpUrlStr


class DataConfig(_Strict):
    providers: list[Literal["yfinance", "stooq", "alphavantage"]]
    earnings_providers: list[Literal["yfinance", "finnhub", "alphavantage"]]
    exchange_calendar: str
    cache_dir: str
    vix_ticker: str
    market_ticker: str
    download_batch_size: PositiveInt
    earnings_history_limit: PositiveInt
    cache_max_age_hours: Annotated[float, Field(gt=0)]
    request_pause_seconds: Annotated[float, Field(ge=0)]
    finnhub_key_env: EnvName
    alphavantage_key_env: EnvName
    sources: DataSources


class GapsConfig(_Strict):
    quantiles: list[Annotated[float, Field(gt=0, lt=1)]]
    drop_thresholds: list[Annotated[float, Field(gt=0, lt=1)]]
    worst_n: PositiveInt


class ConformalConfig(_Strict):
    method: Literal["cqr"]
    mondrian_segments: list[Literal["earnings", "weekend", "holiday", "overnight"]]
    normalize: Literal["none", "ewma"]


class LightGbmConfig(_Strict):
    num_leaves: PositiveInt
    learning_rate: Annotated[float, Field(gt=0)]
    n_estimators: PositiveInt
    min_child_samples: PositiveInt


class WalkForwardConfig(_Strict):
    train_years: PositiveInt
    calibrate_years: PositiveInt
    test_years: PositiveInt


class BaselinesConfig(_Strict):
    ewma_lambda: Annotated[float, Field(gt=0, lt=1)]
    min_ticker_segment_rows: PositiveInt


class AcceptanceConfig(_Strict):
    overall_coverage_tolerance: Fraction
    earnings_coverage_tolerance: Fraction


class ModelConfig(_Strict):
    quantiles: list[Annotated[float, Field(gt=0, lt=1)]]
    target_alpha: Annotated[float, Field(gt=0, lt=1)]
    conformal: ConformalConfig
    lightgbm: LightGbmConfig
    walk_forward: WalkForwardConfig
    baselines: BaselinesConfig
    acceptance: AcceptanceConfig
    seed: int
    n_jobs: int
    target_scaling: Literal["none", "ewma"]

    @model_validator(mode="after")
    def _alpha_is_a_quantile(self) -> ModelConfig:
        if self.target_alpha not in self.quantiles:
            raise ValueError("model.target_alpha must be one of model.quantiles")
        return self


class BorrowerLtv(_Strict):
    low: Fraction
    high: Fraction


class ReplayConfig(_Strict):
    per_segment: PositiveInt
    window_sessions: PositiveInt


class FixedMapConfig(_Strict):
    window_days: PositiveInt
    quantile: Fraction
    min_observations: PositiveInt


class OptionAConfig(_Strict):
    tuning_years: tuple[int, int]
    evaluation_years: tuple[int, int]
    tiers: dict[Literal["weekday", "middle", "weekend"], Fraction]
    tier_sets: list[list[Literal["weekday", "middle", "weekend"]]]
    margin_fractions: list[Fraction]
    lookaheads: list[PositiveInt]
    blend_step: Annotated[float, Field(gt=0, le=1)]
    fixed_map: FixedMapConfig
    universes: list[Literal["vault", "stock_tokens"]]


class OptionBConfig(_Strict):
    tier_set: list[Literal["weekday", "middle", "weekend"]]
    map_fractions: list[Fraction]
    pullback_fractions: list[Fraction]
    lookaheads: list[PositiveInt]


class BacktestConfig(_Strict):
    vault_usdg: Annotated[float, Field(gt=0)]
    supply_apy_by_lltv: dict[str, Annotated[float, Field(ge=0, lt=1)]]
    utilization: Fraction
    loan_turnover_per_session: Fraction
    borrower_ltv_share_of_lltv: BorrowerLtv
    ltv_grid_points: PositiveInt
    session_hours: Annotated[float, Field(gt=0)]
    depth_source: Literal["discovered", "none"]
    tier_pairs_to_tune: list[tuple[Fraction, Fraction]]
    safety_margins_to_tune: list[Fraction]
    lookaheads_to_tune: list[PositiveInt]
    max_worst_event_share: Fraction
    rate_spread_multipliers: list[Annotated[float, Field(ge=0)]]
    turnover_sensitivity: list[Fraction]
    replay: ReplayConfig
    option_a: OptionAConfig
    option_b: OptionBConfig

    def apy(self, lltv: float) -> float:
        """Assumed supply APY for a tier LLTV."""
        key = f"{lltv:g}"
        if key not in self.supply_apy_by_lltv:
            raise KeyError(f"backtest.supply_apy_by_lltv has no entry for LLTV {key}")
        return self.supply_apy_by_lltv[key]


class Range(_Strict):
    low: Annotated[float, Field(ge=0)]
    high: Annotated[float, Field(ge=0)]


class FaucetConfig(_Strict):
    usdg: Annotated[float, Field(gt=0)]
    eth: Annotated[float, Field(gt=0)]
    cooldown_seconds: PositiveInt


class SimConfig(_Strict):
    seed: int
    lenders: PositiveInt
    lender_deposit_usdg: Range
    borrowers_per_market: PositiveInt
    borrow_share_of_market_supply: Fraction
    borrower_ltv_share_of_lltv: Range
    eth_per_actor: Annotated[float, Field(gt=0)]
    testnet_eth_per_actor: Annotated[float, Field(gt=0)]
    faucet: FaucetConfig


class ShockSpec(_Strict):
    symbol: str
    pct: Annotated[float, Field(gt=-1, lt=1)]


class DriftSpec(_Strict):
    symbol: str
    step_pct: Annotated[float, Field(gt=-1, lt=1)]
    steps: PositiveInt
    minutes_per_step: PositiveInt


class DemoConfig(_Strict):
    profile: str
    start: datetime
    max_closes: PositiveInt
    earnings_shock: ShockSpec
    oracle_drift: DriftSpec


class PolicyConfig(_Strict):
    map_fraction: Fraction
    pullback_fraction: Fraction
    turnover_penalty: Annotated[float, Field(ge=0)]
    min_rebalance_usd: Annotated[float, Field(ge=0)]
    min_rebalance_share_of_tvl: Fraction
    lookahead_closed_periods: PositiveInt
    idle_reserve_share: Fraction
    liquidity_min_headroom_share: Fraction


class TriggersConfig(_Strict):
    shock_move_pct: Fraction
    shock_window_min: PositiveInt
    divergence_pct: Fraction
    stale_minutes: PositiveInt


class ScheduleConfig(_Strict):
    tick_seconds: PositiveInt
    hourly: bool
    pre_close_minutes: PositiveInt
    post_open_minutes: PositiveInt
    pre_earnings_hours: PositiveInt
    triggers: TriggersConfig


class ApiConfig(_Strict):
    host_env: EnvName
    port_env: EnvName
    cors_origins_env: EnvName
    admin_token_env: EnvName
    local_web_origin_templates: list[
        Annotated[str, StringConstraints(pattern=r"^https?://.*\{port\}")]
    ]
    web_port_envs: list[EnvName]
    sse_poll_seconds: Annotated[float, Field(gt=0)]
    sse_heartbeat_seconds: Annotated[float, Field(gt=0)]
    almanac_max_days: PositiveInt
    reasons_page_size: PositiveInt


class DiscoverySources(_Strict):
    """Where each discovered fact comes from. Every entry is an official or primary source."""

    robinhood_token_contracts_page: HttpUrlStr
    robinhood_assets_api: HttpUrlStr
    chainlink_feed_directory: HttpUrlStr
    chainlink_feed_docs: HttpUrlStr
    morpho_address_book: HttpUrlStr
    morpho_addresses_docs: HttpUrlStr
    morpho_api: HttpUrlStr
    morpho_blue_interface: HttpUrlStr
    morpho_blue_events: HttpUrlStr
    uniswap_deployments: HttpUrlStr


class OracleStudyConfig(_Strict):
    weekends: PositiveInt
    max_log_block_range: PositiveInt


class PoolScanConfig(_Strict):
    quote_symbols: list[str]
    v3_fee_tiers: list[PositiveInt]
    depth_probe_usd: list[Annotated[float, Field(gt=0)]]


class DiscoveryConfig(_Strict):
    chain: str
    loan_token_symbol: str
    morpho_chain_key: str
    uniswap_chain_id_key: str
    sources: DiscoverySources
    oracle_study: OracleStudyConfig
    pool_scan: PoolScanConfig
    http_timeout_seconds: Annotated[float, Field(gt=0)]
    user_agent: str


class FrozenWindow(_Strict):
    timezone: str
    start_weekday: Annotated[int, Field(ge=0, le=6)]
    start_time: str
    hours: Annotated[float, Field(gt=0)]


class LiveConfig(_Strict):
    profile: str
    discovery_profile: str
    board_cache_seconds: PositiveInt
    quiet_after_minutes: PositiveInt
    frozen_window: FrozenWindow
    market_refresh_minutes: PositiveInt
    lag_blocks: PositiveInt
    examples: PositiveInt
    warm_prices: bool
    refresh_budget_seconds: PositiveInt
    rpc_timeout_seconds: PositiveInt
    rpc_retries: PositiveInt
    logs_from_public_rpc: bool


class FundingConfig(_Strict):
    allocator_eth: PositiveFloat
    curator_eth: PositiveFloat
    keep_deployer_eth: PositiveFloat
    faucet_profile: str


class AlertsConfig(_Strict):
    webhook_env: EnvName
    telegram_api_base: HttpUrlStr
    token_env: EnvName
    poll_timeout_seconds: PositiveInt
    store: str
    max_watches_per_chat: PositiveInt
    refresh_prices: bool
    webhook_secret_env: EnvName
    webhook_secret_header: str
    webhook_path: str


class StateConfig(_Strict):
    kv_url_env: EnvName
    kv_token_env: EnvName
    key_prefix: str
    request_timeout_seconds: PositiveInt
    read_cache_seconds: PositiveInt
    event_poll_seconds: PositiveInt
    cycle_lock_seconds: PositiveInt
    checked_ttl_days: PositiveInt


class AnalyticsConfig(_Strict):
    script_src: HttpUrlStr
    endpoint_domain: str
    endpoint_env: EnvName


class WebConfig(_Strict):
    api_base_url_env: EnvName
    walletconnect_project_id_env: EnvName
    analytics: AnalyticsConfig


class AfterhoursConfig(BaseSettings):
    """The whole configuration. Build it with `load_config`, not directly."""

    model_config = SettingsConfigDict(
        env_prefix="AFTERHOURS_",
        env_nested_delimiter="__",
        env_ignore_empty=True,
        extra="forbid",
        frozen=True,
    )

    active_profile: str
    paths: PathsConfig
    local_node: LocalNodeConfig
    profiles: dict[str, ProfileConfig]
    chains: dict[str, ChainConfig]
    morpho: MorphoConfig
    discovery: DiscoveryConfig
    vault: VaultConfig
    universe: UniverseConfig
    data: DataConfig
    gaps: GapsConfig
    model: ModelConfig
    policy: PolicyConfig
    backtest: BacktestConfig
    sim: SimConfig
    demo: DemoConfig
    schedule: ScheduleConfig
    api: ApiConfig
    web: WebConfig
    alerts: AlertsConfig
    live: LiveConfig
    funding: FundingConfig
    state: StateConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Environment overrides YAML (passed as init kwargs). No dotenv or secrets dir here:
        # `.env` is loaded into the process environment by `load_config`.
        return (env_settings, init_settings)

    @model_validator(mode="after")
    def _references_resolve(self) -> AfterhoursConfig:
        if self.active_profile not in self.profiles:
            raise ValueError(f"active_profile {self.active_profile!r} is not in profiles")
        for name, profile in self.profiles.items():
            if profile.chain not in self.chains:
                raise ValueError(f"profile {name!r} uses unknown chain {profile.chain!r}")
        if self.discovery.chain not in self.chains:
            raise ValueError(f"discovery.chain {self.discovery.chain!r} is not in chains")
        return self

    @property
    def profile(self) -> ProfileConfig:
        """The active profile."""
        return self.profiles[self.active_profile]

    @property
    def chain(self) -> ChainConfig:
        """The chain of the active profile."""
        return self.chains[self.profile.chain]

    def rpc_url(self, profile: str | None = None) -> str:
        """Upstream RPC for a profile: the env var it names, else the chain's public RPC."""
        prof = self.profiles[profile or self.active_profile]
        url = os.environ.get(prof.rpc_env) or self.chains[prof.chain].public_rpc_url
        if not url:
            raise KeyError(f"set {prof.rpc_env} in .env; chain {prof.chain} has no public RPC")
        return url

    def node_url(self, profile: str | None = None) -> str:
        """RPC the bot and deploy use: the local Anvil node for fork/local, else upstream."""
        prof = self.profiles[profile or self.active_profile]
        if prof.local_rpc_port_env:
            port = os.environ.get(prof.local_rpc_port_env)
            if not port:
                raise KeyError(f"set {prof.local_rpc_port_env} (see .env.example)")
            return self.local_node.url_template.format(port=port)
        return self.rpc_url(profile)

    def path(self, relative: str) -> Path:
        """Resolve a repo-relative path from config against the repository root."""
        return REPO_ROOT / relative

    @staticmethod
    def env(name: str | None, *, required: bool = False) -> str | None:
        """Read the environment variable whose *name* is stored in config."""
        if name is None:
            if required:
                raise KeyError("config names no environment variable here")
            return None
        value = os.environ.get(name)
        if required and not value:
            raise KeyError(f"environment variable {name} is not set; see .env.example")
        return value


def config_json_schema() -> dict[str, Any]:
    """The JSON Schema for `config/afterhours.yaml`, generated from the pydantic model."""
    schema = AfterhoursConfig.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"  # hardcode-ok: spec id
    schema["title"] = "Afterhours configuration"
    return schema


def write_schema(path: Path = SCHEMA_PATH) -> Path:
    """Regenerate `config/schema.json`."""
    path.write_text(json.dumps(config_json_schema(), indent=2, sort_keys=True) + "\n")
    return path


def config_path() -> Path:
    """The YAML file to load: `$AFTERHOURS_CONFIG` or the repo default."""
    override = os.environ.get(CONFIG_PATH_ENV)
    return Path(override) if override else DEFAULT_CONFIG_PATH


def load_config(path: Path | None = None, *, load_env_file: bool = True) -> AfterhoursConfig:
    """Load, schema-validate and parse the configuration.

    Raises `jsonschema.ValidationError` for structural problems and
    `pydantic.ValidationError` for semantic ones.
    """
    source = path or config_path()
    raw = yaml.safe_load(source.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{source} must contain a mapping")
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(raw, schema, cls=jsonschema.Draft202012Validator)
    if load_env_file:
        env_file = REPO_ROOT / str(raw.get("paths", {}).get("env_file", ".env"))
        load_dotenv(env_file, override=False)
        # Non-secret defaults (ports, hosts) from the example file, as `make` does.
        load_dotenv(env_file.with_name(env_file.name + ".example"), override=False)
    return AfterhoursConfig(**raw)


@cache
def get_config() -> AfterhoursConfig:
    """Process-wide cached config for long-running services."""
    return load_config()
