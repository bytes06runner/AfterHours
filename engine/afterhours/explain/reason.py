"""Reason cards (SPEC 7.7) and their onchain hash.

`reasonHash = keccak256(RFC 8785 canonical JSON of the card without its "tx" block)`.
The API serves the canonical JSON so a browser can recompute the hash and compare it with the
registry event.

Two deliberate differences from the SPEC sketch: drivers are `{"feature", "contribution",
"detail"}` with `drivers_method` stating how they were computed (the shipped forecaster is a
calibrated baseline, so its split is exact, not SHAP), and `subject` is the stock's weekday
market id, or the vault constant for vault-wide actions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import rfc8785
from eth_utils import keccak

from afterhours.risk.live import Forecast

VAULT_SUBJECT = "0x" + keccak(text="afterhours:vault").hex()
DRIVERS_METHOD = (
    "exact additive split of the calibrated EWMA baseline (volatility, closed hours, segment)"
)


# Fields added after hashing: the tx block (SPEC 7.7) and the hash itself.
NOT_HASHED = ("tx", "reason_hash")


def canonical(card: dict[str, Any]) -> bytes:
    """RFC 8785 bytes of the card without its tx block and stored hash."""
    body = {k: v for k, v in card.items() if k not in NOT_HASHED}
    return bytes(rfc8785.dumps(body))


def reason_hash(card: dict[str, Any]) -> str:
    """keccak256 of the canonical card, 0x-prefixed."""
    return "0x" + keccak(canonical(card)).hex()


def _decimal(x: float, places: int = 6) -> str:
    return f"{x:.{places}f}"


def build_card(
    *,
    profile: str,
    subject: str,
    stock: str,
    action: str,
    from_tier: str | None,
    to_tier: str | None,
    amount_usdg: float,
    forecast: Forecast,
    rule: str,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """A reason card. Floats become fixed-point strings so canonical JSON is stable."""
    return {
        "id": str(uuid.uuid4()),
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
        "profile": profile,
        "subject": subject,
        "stock": stock,
        "action": action,
        "from_tier": from_tier,
        "to_tier": to_tier,
        "amount_usdg": _decimal(amount_usdg, 2),
        "closed_period": forecast.period.to_json() | {"hours": _decimal(forecast.period.hours, 2)},
        "prediction": {
            "alpha": _decimal(forecast.alpha, 4),
            "bad_case_drop": _decimal(forecast.bad_case_drop),
            "model_version": forecast.model_version,
            "method": forecast.method,
        },
        "top_drivers": [
            {
                "feature": d["feature"],
                "contribution": _decimal(float(d["contribution"])),
                "detail": d["detail"],
            }
            for d in sorted(forecast.drivers, key=lambda d: -abs(float(d["contribution"])))
        ],
        "drivers_method": DRIVERS_METHOD,
        "rule_fired": rule,
    }
