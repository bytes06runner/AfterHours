"""The MCP server end to end: tool list, read-only hints, calls against a stub Afterhours API."""

from __future__ import annotations

import json
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from mcp import Client, StdioServerParameters

from afterhours_mcp import server

RISK = {"symbol": "NVDA", "summary": "Frozen since Friday 20:00 New York.", "bad_case_drop": 0.071}
CALLS: list[str] = []


class Stub(BaseHTTPRequestHandler):
    warming = 1  # the first weekend-risk call answers "still reading"

    def do_GET(self) -> None:
        CALLS.append(self.path)
        if self.path == "/v1/agent/market-status":
            self._send(200, {"session": "closed", "summary": "The US stock exchange is closed."})
        elif self.path == "/v1/agent/weekend-risk/NVDA":
            if Stub.warming:
                Stub.warming -= 1
                self._send(503, {"detail": "Still reading"}, {"Retry-After": "0"})
            else:
                self._send(200, RISK)
        elif self.path.startswith("/v1/agent/weekend-risk/"):
            self._send(404, {"detail": "No Stock Token 'XYZ'. Known: NVDA."})
        else:
            self._send(404, {"detail": "Not found"})

    def _send(self, code: int, body: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{httpd.server_address[1]}"
    monkeypatch.setenv("AFTERHOURS_API_URL", url)
    monkeypatch.setenv("AFTERHOURS_TIMEOUT_SECONDS", "10")
    Stub.warming = 1
    CALLS.clear()
    yield url
    httpd.shutdown()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_tools_are_listed_read_only() -> None:
    async with Client(server.mcp) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert set(tools) == {"market_status", "get_weekend_risk", "check_position", "explain_move"}
    for t in tools.values():
        assert t.annotations is not None
        assert t.annotations.read_only_hint is True
        assert t.annotations.destructive_hint is False
        assert t.description


@pytest.mark.anyio
async def test_calls_reach_the_api_and_wait_while_it_warms(api: str) -> None:
    async with Client(server.mcp) as client:
        status = await client.call_tool("market_status", {})
        assert status.structured_content["session"] == "closed"
        risk = await client.call_tool("get_weekend_risk", {"ticker": "nvda"})
        assert risk.structured_content["summary"].startswith("Frozen")
    # "still reading" (503) was retried, not surfaced
    assert CALLS.count("/v1/agent/weekend-risk/NVDA") == 2


@pytest.mark.anyio
async def test_errors_are_plain(api: str) -> None:
    async with Client(server.mcp) as client:
        bad = await client.call_tool("get_weekend_risk", {"ticker": "XYZ"})
        assert bad.is_error
        assert "Known: NVDA" in bad.content[0].text
        wallet = await client.call_tool("check_position", {"address": "not-an-address"})
        assert wallet.is_error
        assert "is not a 0x address" in wallet.content[0].text
    assert not any(c.startswith("/v1/agent/positions") for c in CALLS)  # rejected before a call


@pytest.mark.anyio
async def test_stdio_entry_point(api: str) -> None:
    # What Claude Desktop does: start the server as a subprocess and talk over stdio.
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "afterhours_mcp.server"],
        env={"AFTERHOURS_API_URL": api, "AFTERHOURS_TIMEOUT_SECONDS": "10"},
    )
    async with Client(params) as client:
        res = await client.call_tool("market_status", {})
    assert res.structured_content["summary"] == "The US stock exchange is closed."
