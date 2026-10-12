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


def parse_event(raw: str | bytes) -> Comment | None:
    try:
        message = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(message, dict) or message.get("event") != "chat":
        return None
    data = message.get("data")
    if not isinstance(data, dict):
        return None
    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    user_id = str(data.get("uniqueId") or user.get("uniqueId") or "").strip()
    nickname = str(data.get("nickname") or user.get("nickname") or "")
    text = str(data.get("comment") or "")
    if not user_id or not text:
        return None
    return Comment(user_id, nickname, text)


async def comments(url: str) -> AsyncIterator[Comment]:
    warned = False
    while True:
        try:
            async with connect(url, open_timeout=10) as ws:
                log.info("Connected to IndoFinity at %s", url)
                warned = False
                async for raw in ws:
                    comment = parse_event(raw)
                    if comment is not None:
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
