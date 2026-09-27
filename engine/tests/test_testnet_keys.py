"""`make testnet-keys`: writes four keys into .env, prints addresses only, never overwrites."""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest
from eth_account import Account
from typer.testing import CliRunner

from afterhours import deploy
from afterhours.cli import app
from afterhours.config import load_config
from afterhours.deploy import ROLES, write_testnet_keys

KEY = re.compile(r"0x[0-9a-fA-F]{64}")
EXAMPLE = (
    "# comment\nRH_TESTNET_RPC_URL=\n"
    "DEPLOYER_PK=\nCURATOR_PK=\nALLOCATOR_PK=\nGUARDIAN_PK=\nAPI_PORT=8000\n"
)


def fake_key() -> str:
    key: str = Account.create().key.hex()
    return key if key.startswith("0x") else "0x" + key


def values(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def test_fills_empty_lines_in_place(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(EXAMPLE)
    who = write_testnet_keys(env, fake_key)
    got = values(env)
    assert set(who) == set(ROLES)
    for role in ROLES:
        assert KEY.fullmatch(got[role])
        assert who[role] == Account.from_key(got[role]).address
    assert got["API_PORT"] == "8000"  # other lines kept
    assert env.read_text().startswith("# comment\n")
    assert len(env.read_text().splitlines()) == len(EXAMPLE.splitlines())  # no duplicates
    assert stat.S_IMODE(env.stat().st_mode) == 0o600


def test_creates_the_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    write_testnet_keys(env, fake_key)
    assert set(values(env)) == set(ROLES)


@pytest.mark.parametrize(
    "line", ["CURATOR_PK=0xabc", "export CURATOR_PK='0xabc'", " CURATOR_PK = x"]
)
def test_never_overwrites(tmp_path: Path, line: str) -> None:
    env = tmp_path / ".env"
    before = EXAMPLE.replace("CURATOR_PK=\n", line + "\n")
    env.write_text(before)
    with pytest.raises(KeyError) as err:
        write_testnet_keys(env, fake_key)
    assert "CURATOR_PK" in str(err.value)
    assert "0xabc" not in str(err.value)
    assert env.read_text() == before  # untouched


def test_cli_prints_addresses_never_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / ".env"
    env.write_text(EXAMPLE)
    monkeypatch.setenv("AFTERHOURS_PATHS__ENV_FILE", str(env))
    monkeypatch.setattr(deploy, "cast_wallet_new", fake_key)
    out = CliRunner().invoke(app, ["testnet-keys"])
    assert out.exit_code == 0, out.output
    keys = [values(env)[r] for r in ROLES]
    for key in keys:
        assert key[2:].lower() not in out.output.lower()
    assert not KEY.search(out.output)
    cfg = load_config(load_env_file=False)
    chain = cfg.chains[cfg.profiles[cfg.funding.faucet_profile].chain]
    assert chain.faucet_url
    assert chain.faucet_url in out.output
    deployer = Account.from_key(values(env)["DEPLOYER_PK"]).address
    assert f"Deployer address: {deployer}" in out.output
    # A second run refuses and changes nothing.
    again = CliRunner().invoke(app, ["testnet-keys"])
    assert again.exit_code != 0
    assert [values(env)[r] for r in ROLES] == keys
