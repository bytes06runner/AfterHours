"""No RPC key or bot token reaches a log line."""

from __future__ import annotations

import logging

import pytest

import afterhours  # noqa: F401  (installs the redaction)
from afterhours.logsafe import redact


def test_redact() -> None:
    assert redact("429 for url: https://rpc.example.org/v2/SECRETKEY") == (
        "429 for url: https://rpc.example.org/[redacted]"
    )
    assert "TOKEN" not in redact("POST https://api.example.org/botTOKEN:abc/sendMessage failed")
    assert redact("no url here") == "no url here"


def test_every_log_record_is_redacted(caplog: pytest.LogCaptureFixture) -> None:
    log = logging.getLogger("afterhours.test")
    err = RuntimeError("429 Client Error for url: https://rpc.example.org/v2/SECRETKEY")
    with caplog.at_level(logging.WARNING):
        log.warning("live read failed: %s", err)
        try:
            raise err
        except RuntimeError:
            log.exception("with traceback")
    text = caplog.text
    assert "SECRETKEY" not in text
    assert "https://rpc.example.org/[redacted]" in text
