"""Telegram alerts: before each close, warn subscribers whose stock or position looks risky tonight.

Read-only. Commands arrive either by long polling (`getUpdates`, `afterhours alerts run`) or by
webhook (`setWebhook`, handled by the API; core.telegram.org/bots/api). Subscriptions live in
`paths.state_dir/<alerts.store>`, or in the shared store when one is configured (`state`). Once
per session, inside the pre-close window (`schedule.pre_close_minutes` before the close), every
subscription is checked (`afterhours alerts check`, or the polling loop):

- a stock alerts when tonight's forecast bad case reaches the cushion of one of its mainnet
  Morpho markets (the risk board's `breached` list);
- an address alerts when tonight's bad case reaches one of its positions' drop to liquidation.

Each subscription is checked once per close. The token is read from the environment variable named
in `alerts.token_env`; it is never logged.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from eth_utils.address import is_address, to_checksum_address

from afterhours.bot.scheduler import pre_close_window as check_window
from afterhours.config import AfterhoursConfig
from afterhours.kv import KV, kv_from_config

log = logging.getLogger(__name__)

HELP = (
    "Afterhours alerts. Before each US market close I check tonight's forecast for what you follow "
    "and message you only if it looks risky.\n\n"
    "/watch NVDA  follow a Stock Token\n"
    "/watch 0x...  follow a wallet's Morpho positions on {network}\n"
    "/unwatch NVDA or /unwatch 0x...  stop following one\n"
    "/list  what you follow\n"
    "/stop  stop everything\n\n"
    "Read-only: I never ask for keys or move funds. The forecast is a model's bad case, not advice."
)


# ---------------------------------------------------------------------- Telegram client
class Chat(Protocol):
    def updates(self, offset: int | None) -> list[dict[str, Any]]: ...
    def send(self, chat_id: int, text: str) -> None: ...


class Telegram:
    """The two Bot API methods the bot needs, over plain HTTPS."""

    def __init__(self, api_base: str, token: str, poll_timeout: int) -> None:
        self._url = f"{api_base.rstrip('/')}/bot{token}/"
        self._timeout = poll_timeout
        self._http = httpx.Client(timeout=poll_timeout + 10)

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        try:
            res = self._http.post(self._url + method, json=payload)
            body = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            # The URL carries the token, so log only the error type.
            raise RuntimeError(f"telegram {method} failed: {type(exc).__name__}") from None
        if not body.get("ok"):
            raise RuntimeError(f"telegram {method}: {body.get('description', 'not ok')}")
        return body["result"]

    def updates(self, offset: int | None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": self._timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload["offset"] = offset
        result: list[dict[str, Any]] = self._call("getUpdates", payload)
        return result

    def send(self, chat_id: int, text: str) -> None:
        self._call("sendMessage", {"chat_id": chat_id, "text": text})

    def set_webhook(self, url: str, secret: str) -> None:
        self._call(
            "setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["message"]}
        )

    def delete_webhook(self) -> None:
        self._call("deleteWebhook", {})

    def webhook_info(self) -> dict[str, Any]:
        info: dict[str, Any] = self._call("getWebhookInfo", {})
        return info


# ---------------------------------------------------------------------- subscriptions
@dataclass
class Store:
    """Subscriptions and delivery bookkeeping: a JSON file, or the shared store (Redis).

    In the shared store, chats are one hash field each and the pre-close bookkeeping is its own
    key, so the API (answering commands) and a scheduled job (sending alerts) never overwrite
    each other's writes.
    """

    path: Path | None = None
    kv: KV | None = None
    checked_ttl_seconds: int = 0
    offset: int | None = None
    chats: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    checked: dict[str, list[str]] = field(default_factory=dict)  # close iso -> "chat|target"

    @classmethod
    def load(cls, path: Path) -> Store:
        if not path.exists():
            return cls(path)
        doc = json.loads(path.read_text())
        return cls(
            path,
            offset=doc.get("offset"),
            chats=doc.get("chats", {}),
            checked=doc.get("checked", {}),
        )

    @classmethod
    def load_kv(cls, kv: KV, checked_ttl_seconds: int) -> Store:
        flat = kv.cmd("HGETALL", kv.key("alerts", "chats")) or []
        chats = {flat[i]: json.loads(flat[i + 1]) for i in range(0, len(flat), 2)}
        raw = kv.cmd("GET", kv.key("alerts", "checked"))
        return cls(
            kv=kv,
            checked_ttl_seconds=checked_ttl_seconds,
            chats=chats,
            checked=json.loads(raw) if raw else {},
        )

    @classmethod
    def from_config(cls, cfg: AfterhoursConfig) -> Store:
        kv = kv_from_config(cfg)
        if kv is not None:
            return cls.load_kv(kv, cfg.state.checked_ttl_days * 86400)
        return cls.load(cfg.path(cfg.paths.state_dir) / cfg.alerts.store)

    def _write_file(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        doc = {"offset": self.offset, "chats": self.chats, "checked": self.checked}
        tmp.write_text(json.dumps(doc, indent=2, sort_keys=True))
        tmp.replace(self.path)

    def save_chat(self, chat: int) -> None:
        """Persist one chat's subscriptions (or their removal)."""
        if self.kv is None:
            self._write_file()
            return
        key, name = self.kv.key("alerts", "chats"), str(chat)
        if name in self.chats:
            self.kv.cmd("HSET", key, name, json.dumps(self.chats[name]))
        else:
            self.kv.cmd("HDEL", key, name)

    def save_checked(self) -> None:
        if self.kv is None:
            self._write_file()
            return
        key = self.kv.key("alerts", "checked")
        self.kv.cmd("SET", key, json.dumps(self.checked), "EX", self.checked_ttl_seconds)

    def save_offset(self) -> None:
        """Only polling uses an offset; webhooks need none."""
        self._write_file()

    def watches(self, chat: int) -> dict[str, list[str]]:
        return self.chats.setdefault(str(chat), {"symbols": [], "addresses": []})


def handle(  # noqa: PLR0911 (one reply per command and error)
    store: Store, chat: int, text: str, symbols: set[str], network: str, limit: int
) -> str:
    """Apply one command and return the reply."""
    parts = text.strip().split()
    if not parts:
        return HELP.format(network=network)
    cmd = parts[0].split("@")[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    if cmd in ("/start", "/help"):
        return HELP.format(network=network)
    if cmd == "/stop":
        store.chats.pop(str(chat), None)
        return "Stopped. You follow nothing now. Send /watch to start again."
    w = store.watches(chat)
    if cmd == "/list":
        if not w["symbols"] and not w["addresses"]:
            return "You follow nothing yet. Try /watch NVDA or /watch 0x..."
        lines = [f"Stocks: {', '.join(w['symbols']) or 'none'}"]
        lines.append(f"Addresses: {', '.join(w['addresses']) or 'none'}")
        return "\n".join(lines)
    if cmd not in ("/watch", "/unwatch"):
        return "I did not understand that. Send /help for the commands."
    if not arg:
        return f"Add a stock or an address, for example {cmd} NVDA."
    if is_address(arg):
        key, value = "addresses", str(to_checksum_address(arg))
    elif arg.upper() in symbols:
        key, value = "symbols", arg.upper()
    else:
        return f"{arg} is not a Stock Token with a live feed or a wallet address."
    if cmd == "/unwatch":
        if value in w[key]:
            w[key].remove(value)
            return f"Stopped following {value}."
        return f"You were not following {value}."
    if value in w[key]:
        return f"You already follow {value}."
    if len(w["symbols"]) + len(w["addresses"]) >= limit:
        return f"You can follow up to {limit} stocks and addresses. Send /unwatch to free one."
    w[key].append(value)
    return f"Following {value}. I will message you before a close only if tonight looks risky."


def handle_update(
    store: Store, update: dict[str, Any], symbols: set[str], network: str, limit: int
) -> tuple[int, str] | None:
    """One Telegram update: apply its command, save that chat, return (chat, reply)."""
    msg = update.get("message") or {}
    text, chat = msg.get("text"), (msg.get("chat") or {}).get("id")
    if not text or chat is None:
        return None
    reply = handle(store, int(chat), text, symbols, network, limit)
    if str(chat) in store.chats and not any(store.chats[str(chat)].values()):
        store.chats.pop(str(chat))  # nothing followed: keep no record of the chat
    store.save_chat(int(chat))
    return int(chat), reply


# ---------------------------------------------------------------------- the checks
def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def stock_alert(row: dict[str, Any]) -> str | None:
    """The alert for one risk board row, or None when no market's cushion is reached."""
    f = row.get("tonight")
    if not f or not row.get("breached"):
        return None
    worst = min(row["breached"])
    cushion = next(c["cushion"] for c in row["markets"] if c["lltv"] == worst)
    lltvs = ", ".join(pct(lv) for lv in sorted(row["breached"], reverse=True))
    return (
        f"{row['symbol']}: tonight's forecast bad case is a {pct(f['bad_case_drop'])} drop "
        f"({f['period']['hours']:.0f} hours closed). That reaches the cushion of its "
        f"{lltvs} loan-to-value Morpho markets (the tightest cushion is {pct(cushion)}). "
        "Borrowers near the limit there may be liquidated when trading resumes."
    )


def position_alerts(address: str, doc: dict[str, Any]) -> list[str]:
    """One alert per position whose drop to liquidation is within tonight's bad case."""
    out = []
    for p in doc.get("positions", []):
        if not p.get("breach_tonight"):
            continue
        f = p["tonight"]
        out.append(
            f"{address[:6]}...{address[-4:]} {p['symbol']} position: it is liquidated if the price "
            f"falls to {p['liquidation_price']:,.2f}, {pct(p['drop_to_liquidation'])} below now. "
            f"Tonight's forecast bad case is a {pct(f['bad_case_drop'])} drop. "
            "Adding collateral or repaying some of the loan widens the gap."
        )
    return out


class Source(Protocol):
    @property
    def feeds(self) -> Mapping[str, object]: ...  # symbol -> feed address

    def board(self, now: datetime | None = None, *, wait: bool = False) -> dict[str, Any]: ...
    def positions(self, address: str, now: datetime | None = None) -> dict[str, Any]: ...


def run_checks(
    store: Store, source: Source, close: datetime, now: datetime
) -> list[tuple[int, str]]:
    """Messages due for this close; marks every subscription checked once, alert or not."""
    key = close.astimezone(UTC).isoformat()
    done = set(store.checked.get(key, []))
    due: list[tuple[int, str]] = []
    board: dict[str, Any] | None = None
    positions: dict[str, dict[str, Any]] = {}
    for chat, w in store.chats.items():
        for sym in w["symbols"]:
            tag = f"{chat}|{sym}"
            if tag in done:
                continue
            board = board or source.board(now, wait=True)  # a job has no cached board
            row = next((r for r in board["stocks"] if r["symbol"] == sym), None)
            msg = stock_alert(row) if row else None
            if msg:
                due.append((int(chat), msg))
            done.add(tag)
        for addr in w["addresses"]:
            tag = f"{chat}|{addr}"
            if tag in done:
                continue
            if addr not in positions:
                positions[addr] = source.positions(addr, now)
            due.extend((int(chat), m) for m in position_alerts(addr, positions[addr]))
            done.add(tag)
    # Keep only the current close's bookkeeping.
    store.checked = {key: sorted(done)}
    return due


# ---------------------------------------------------------------------- the loop
class AlertBot:
    def __init__(
        self,
        cfg: AfterhoursConfig,
        source: Source,
        chat: Chat,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        refresh: Callable[[], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.source = source
        self.chat = chat
        self.clock = clock
        self.refresh = refresh
        self.store = Store.from_config(cfg)
        profile = cfg.profiles[cfg.live.profile]
        self.network = cfg.chains[profile.chain].name
        self._refreshed: datetime | None = None

    def poll(self) -> None:
        """Answer the commands that arrived since the last poll."""
        for u in self.chat.updates(self.store.offset):
            self.store.offset = int(u["update_id"]) + 1
            answer = handle_update(
                self.store,
                u,
                set(self.source.feeds),
                self.network,
                self.cfg.alerts.max_watches_per_chat,
            )
            if answer:
                self.chat.send(*answer)
        self.store.save_offset()

    def check(self) -> int:
        """Inside a pre-close window, send what is due. Returns messages sent."""
        now = self.clock()
        close = check_window(self.cfg, now)
        if close is None:
            return 0
        if self.refresh and self._refreshed != close:
            self.refresh()
            self._refreshed = close
        if self.store.kv is not None:
            self.store = Store.from_config(self.cfg)  # the API may have added subscriptions
        sent = 0
        for chat, text in run_checks(self.store, self.source, close, now):
            try:
                self.chat.send(chat, text)
                sent += 1
            except RuntimeError as exc:
                log.warning("alert to one chat failed: %s", exc)
        self.store.save_checked()
        if sent:
            log.info("sent %d alerts before the %s close", sent, close.isoformat())
        return sent

    def run(self) -> None:
        log.info("alert bot running on %s", self.network)
        while True:
            try:
                self.poll()
                self.check()
            except Exception as exc:  # keep serving: a failed RPC or API call is retried
                log.warning("alert loop: %s", exc)
                time.sleep(self.cfg.alerts.poll_timeout_seconds)


def telegram_from_config(cfg: AfterhoursConfig) -> Telegram:
    token = cfg.env(cfg.alerts.token_env)
    if not token:
        raise RuntimeError(
            f"{cfg.alerts.token_env} is not set: "
            "create a bot with @BotFather and put its token in .env"
        )
    return Telegram(cfg.alerts.telegram_api_base, token, cfg.alerts.poll_timeout_seconds)
