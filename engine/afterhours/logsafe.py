"""Keep secrets out of logs: redact URL paths and queries in every log record.

RPC providers put the API key in the URL path (Alchemy: /v2/<key>) and Telegram puts the bot
token there (/bot<token>/...). Exceptions from requests and httpx quote the full URL, and our
code logs exceptions, so without this a rate-limit error would write the key into the host's
logs. The host name stays, so a log line still says which service failed.
"""

from __future__ import annotations

import logging
import re
from typing import Any

URL_PATH = re.compile(r"(https?://[^/\s'\"<>]+)/[^\s'\"<>)]*")


def redact(text: str) -> str:
    """A URL keeps its scheme and host; its path and query become `/[redacted]`."""
    return URL_PATH.sub(r"\1/[redacted]", text)


def _clean(value: Any) -> Any:
    if isinstance(value, BaseException | str):
        return redact(str(value))
    return value


def install() -> None:
    """Redact every record created from now on, whichever logger or handler it reaches."""
    old = logging.getLogRecordFactory()
    if getattr(old, "_afterhours_redacts", False):
        return

    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = old(*args, **kwargs)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_clean(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _clean(v) for k, v in record.args.items()}
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = redact(logging.Formatter().formatException(record.exc_info))
            record.exc_info = None
        return record

    factory._afterhours_redacts = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)
