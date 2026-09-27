"""An in-memory stand-in for Upstash's REST API, with the Redis commands the engine uses."""

from __future__ import annotations

import json
from typing import Any

import httpx

from afterhours.kv import KV

TOKEN = "test-token"


class FakeUpstash:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.calls = 0

    def run(self, cmd: list[str]) -> Any:  # noqa: PLR0911 (one branch per command)
        self.calls += 1
        name, args = cmd[0].upper(), cmd[1:]
        d = self.data
        if name == "GET":
            return d.get(args[0])
        if name == "SET":
            key, value, opts = args[0], args[1], [a.upper() for a in args[2:]]
            if "NX" in opts and key in d:
                return None
            d[key] = value
            return "OK"
        if name == "DEL":
            return int(d.pop(args[0], None) is not None)
        if name == "RPUSH":
            d.setdefault(args[0], []).extend(args[1:])
            return len(d[args[0]])
        if name == "LLEN":
            return len(d.get(args[0], []))
        if name == "LRANGE":
            items = d.get(args[0], [])
            start, stop = int(args[1]), int(args[2])
            return items[start : (None if stop == -1 else stop + 1)]
        if name == "HSET":
            d.setdefault(args[0], {})[args[1]] = args[2]
            return 1
        if name == "HDEL":
            return int(d.get(args[0], {}).pop(args[1], None) is not None)
        if name == "HGETALL":
            return [x for kv in d.get(args[0], {}).items() for x in kv]
        if name == "EVAL":  # only the unlock script: delete KEYS[1] if it holds ARGV[1]
            key, token = args[2], args[3]
            if d.get(key) == token:
                del d[key]
                return 1
            return 0
        raise NotImplementedError(name)

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"error": "Unauthorized"})
        body = json.loads(request.content)
        if request.url.path.endswith("/pipeline"):
            return httpx.Response(200, json=[{"result": self.run(c)} for c in body])
        return httpx.Response(200, json={"result": self.run(body)})

    def kv(self, prefix: str = "test") -> KV:
        return KV("https://kv.test", TOKEN, prefix, 5, transport=httpx.MockTransport(self.handler))
