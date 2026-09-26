"""Tests for the configuration loader."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pydantic
import pytest
import yaml

from afterhours.config import (
    DEFAULT_CONFIG_PATH,
    SCHEMA_PATH,
    config_json_schema,
    load_config,
)
from afterhours.public_config import public_config


def _write(tmp_path: Path, mutate: dict[str, object] | None = None) -> Path:
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())
    for dotted, value in (mutate or {}).items():
        node = raw
        *parents, leaf = dotted.split(".")
        for part in parents:
            node = node[part]
        node[leaf] = value
    out = tmp_path / "afterhours.yaml"
    out.write_text(yaml.safe_dump(raw))
    return out


def test_repo_config_loads() -> None:
    cfg = load_config(load_env_file=False)
    assert cfg.active_profile in cfg.profiles
    assert cfg.profile.chain in cfg.chains
    assert cfg.model.target_alpha in cfg.model.quantiles


def test_schema_file_is_up_to_date() -> None:
    committed = json.loads(SCHEMA_PATH.read_text())
    assert committed == config_json_schema(), "run `make gen-schema`"


def test_yaml_change_is_visible(tmp_path: Path) -> None:
    cfg = load_config(_write(tmp_path, {"vault.symbol": "ahTEST"}), load_env_file=False)
    assert cfg.vault.symbol == "ahTEST"
    assert public_config(cfg)["vault"]["symbol"] == "ahTEST"


def test_env_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AFTERHOURS_ACTIVE_PROFILE", "arb-sepolia")
    cfg = load_config(_write(tmp_path), load_env_file=False)
    assert cfg.active_profile == "arb-sepolia"
    assert cfg.chain is cfg.chains["arbitrum-sepolia"]


def test_unknown_key_rejected_by_schema(tmp_path: Path) -> None:
    with pytest.raises(jsonschema.ValidationError):
        load_config(_write(tmp_path, {"vault.surprise": 1}), load_env_file=False)


def test_wrong_type_rejected(tmp_path: Path) -> None:
    with pytest.raises(jsonschema.ValidationError):
        load_config(_write(tmp_path, {"policy.safety_margin": "high"}), load_env_file=False)


def test_unknown_active_profile_rejected(tmp_path: Path) -> None:
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, {"active_profile": "nowhere"}), load_env_file=False)


def test_target_alpha_must_be_a_quantile(tmp_path: Path) -> None:
    with pytest.raises(pydantic.ValidationError):
        load_config(_write(tmp_path, {"model.target_alpha": 0.02}), load_env_file=False)


def test_env_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = load_config(load_env_file=False)
    monkeypatch.setenv("AH_TEST_VAR", "x")
    assert cfg.env("AH_TEST_VAR") == "x"
    monkeypatch.delenv("AH_TEST_VAR")
    with pytest.raises(KeyError):
        cfg.env("AH_TEST_VAR", required=True)
