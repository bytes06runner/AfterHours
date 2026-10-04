"""Capture a real example session for the Agents page: real tool calls, real answers.

Starts the MCP server the way an MCP client does (a stdio subprocess; by default the same
`uvx --from git+...#subdirectory=agents afterhours-mcp` command the install steps give), calls
all four tools against AFTERHOURS_API_URL, and writes artifacts/agents/example-session.json.
The questions are examples of what a person might ask; every answer is what the tool returned.

    AFTERHOURS_API_URL=... uv run python agents/scripts/capture_example.py [--local]
        [--source git+...#subdirectory=agents]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anyio
from mcp import Client, StdioServerParameters

REPO = Path(__file__).resolve().parents[2]


def get(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=120) as res:
        return json.loads(res.read().decode())


async def run(params: StdioServerParameters, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    async with Client(params) as client:
        tools = [t.name for t in (await client.list_tools()).tools]
        out.append({"listed_tools": tools})
        for step in steps:
            res = await client.call_tool(step["tool"], step["arguments"])
            body = res.structured_content or {}
            out.append({**step, "is_error": bool(res.is_error), "result": body})
            text = body.get("summary", res.content[0].text if res.content else "")
            print(f"{step['tool']}: {text[:160]}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="run the server from this checkout")
    ap.add_argument("--source", help="uvx --from source (default: the README's GitHub source)")
    args = ap.parse_args()
    api = os.environ["AFTERHOURS_API_URL"].rstrip("/")
    readme = (REPO / "agents" / "README.md").read_text()
    source = args.source or readme.split('"--from", "', 1)[1].split('"', 1)[0]
    env = {**os.environ, "AFTERHOURS_API_URL": api, "AFTERHOURS_TIMEOUT_SECONDS": "180"}
    if args.local:
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "afterhours_mcp.server"], env=env
        )
        how = "python -m afterhours_mcp.server (this checkout)"
    else:
        params = StdioServerParameters(
            command="uvx", args=["--from", source, "afterhours-mcp"], env=env
        )
        how = f"uvx --from {source} afterhours-mcp"
    borrower = get(f"{api}/v1/live/examples")["addresses"][0]
    reason = get(f"{api}/v1/reasons")["items"][0]["id"]
    risk = get(f"{api}/v1/live/regimes")
    weakest = min(
        (t for t in risk["tokens"] if t["quality"]["score"] is not None),
        key=lambda t: t["quality"]["score"],
    )["symbol"]
    steps = [
        {
            "question": "Is the stock market open right now?",
            "tool": "market_status",
            "arguments": {},
        },
        {
            "question": "Is NVDA safe to lend against this weekend?",
            "tool": "get_weekend_risk",
            "arguments": {"ticker": "NVDA"},
        },
        {
            "question": f"Which price should I trust least right now? Check {weakest}.",
            "tool": "get_weekend_risk",
            "arguments": {"ticker": weakest},
        },
        {
            "question": "Could tonight's gap liquidate this wallet?",
            "tool": "check_position",
            "arguments": {"address": borrower},
        },
        {
            "question": "Why did the vault make its latest move?",
            "tool": "explain_move",
            "arguments": {"reason_id": reason},
        },
    ]
    session = anyio.run(run, params, steps)
    doc = {
        "captured_at": datetime.now(UTC).isoformat(),
        "api": api,
        "server_started_with": how,
        "note": "Questions are examples; every tool call and answer is real, from the API above.",
        "session": session,
    }
    out = REPO / "artifacts" / "agents" / "example-session.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
