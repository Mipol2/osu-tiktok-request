from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

RECONNECT_DELAY = 3

log = logging.getLogger("osureq.indofinity")


@dataclass(frozen=True)
class Comment:
    user_id: str
    nickname: str
    text: str

    @property
    def display_name(self) -> str:
        return self.nickname.strip() or self.user_id


CHAT_EVENTS = {"chat", "comment", "message"}
TEXT_KEYS = ("comment", "content", "message", "text", "msg")
ID_KEYS = ("uniqueId", "unique_id", "username", "userId", "user_id")
NAME_KEYS = ("nickname", "nickName", "displayName", "display_name")


def _loads(value):
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def _first(sources: list[dict], keys: tuple[str, ...]) -> str:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""


def parse_event(raw: str | bytes) -> Comment | None:
    message = _loads(raw)
    if not isinstance(message, dict):
        return None
    event = str(message.get("event") or message.get("type") or "").lower()
    if event not in CHAT_EVENTS:
        return None
    data = _loads(message.get("data"))
    if not isinstance(data, dict):
        return None
    user = _loads(data.get("user"))
    sources = [data, user] if isinstance(user, dict) else [data]
    text = _first([data], TEXT_KEYS)
    if not text:
        return None
    nickname = _first(sources, NAME_KEYS)
    user_id = _first(sources, ID_KEYS) or nickname or "unknown"
    return Comment(user_id, nickname, text)


async def comments(url: str) -> AsyncIterator[Comment]:
    warned = False
    while True:
        try:
            async with connect(url, open_timeout=10) as ws:
                log.info("Connected to IndoFinity at %s", url)
                warned = False
                async for raw in ws:
                    log.debug("IndoFinity event: %s", raw[:600] if isinstance(raw, str) else raw[:600])
                    comment = parse_event(raw)
                    if comment is None:
                        continue
                    log.debug("Chat from %s (%s): %r", comment.display_name, comment.user_id, comment.text)
                    yield comment
            log.warning("IndoFinity closed the connection, reconnecting")
        except (OSError, WebSocketException, asyncio.TimeoutError) as e:
            if not warned:
                log.warning(
                    "Cannot reach IndoFinity at %s (%s). Is the desktop app open and connected to your live? "
                    "Retrying every %ss.",
                    url,
                    e or type(e).__name__,
                    RECONNECT_DELAY,
                )
                warned = True
        await asyncio.sleep(RECONNECT_DELAY)
