"""A small client for Upstash Redis over its REST API (upstash.com/docs/redis/features/restapi).

Commands go as a JSON array in a POST body with `Authorization: Bearer <token>`; `/pipeline`
takes a list of them. HTTPS only, so it needs no Redis driver and works from short-lived jobs.
"""

from __future__ import annotations

from typing import Any

import httpx

from afterhours.config import AfterhoursConfig


class KVError(RuntimeError):
    pass


class KV:
    def __init__(
        self,
        url: str,
        token: str,
        prefix: str,
        timeout: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.prefix = prefix
        self._http = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
        )

    def key(self, *parts: str) -> str:
        return ":".join((self.prefix, *parts))

    def _post(self, path: str, body: Any) -> Any:
        try:
            res = self._http.post(path, json=body)
            doc = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            # Never include the request (it carries the token), only what went wrong.
            raise KVError(f"kv request failed: {type(exc).__name__}") from None
        if isinstance(doc, dict) and "error" in doc:
            raise KVError(f"kv: {doc['error']}")
        return doc

    def cmd(self, *args: Any) -> Any:
        return self._post("/", [str(a) for a in args])["result"]

    def pipeline(self, commands: list[list[Any]]) -> list[Any]:
        if not commands:
            return []
        out = self._post("/pipeline", [[str(a) for a in c] for c in commands])
        errors = [r["error"] for r in out if "error" in r]
        if errors:
            raise KVError(f"kv: {errors[0]}")
        return [r["result"] for r in out]


def kv_from_config(
    cfg: AfterhoursConfig, transport: httpx.BaseTransport | None = None
) -> KV | None:
    """The shared store when both env vars are set, else None (file mode)."""
    url = cfg.env(cfg.state.kv_url_env)
    token = cfg.env(cfg.state.kv_token_env)
    if not url or not token:
        return None
    return KV(
        url, token, cfg.state.key_prefix, cfg.state.request_timeout_seconds, transport=transport
    )
