from __future__ import annotations

import logging
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from .commands import Request, parse
from .config import Config, Filters
from .indofinity import Comment
from .osu_api import ApiError, Beatmap, OsuApi, adjusted_length

log = logging.getLogger("osureq")


class Outcome(str, Enum):
    IGNORED = "ignored"
    BLOCKED = "blocked"
    COOLDOWN = "cooldown"
    DUPLICATE = "duplicate"
    NOT_FOUND = "not_found"
    REJECTED = "rejected"
    ERROR = "error"
    SENT = "sent"


class Sender(Protocol):
    async def send(self, target: str, text: str) -> None: ...


def format_length(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def check_filters(beatmap: Beatmap, mods: tuple[str, ...], filters: Filters) -> str | None:
    if filters.modes and beatmap.mode not in filters.modes:
        return f"mode {beatmap.mode} is not allowed"
    if filters.statuses and beatmap.status not in filters.statuses:
        return f"status {beatmap.status} is not allowed"
    if filters.min_stars is not None and beatmap.stars < filters.min_stars:
        return f"{beatmap.stars:.2f}* is below the minimum of {filters.min_stars}*"
    if filters.max_stars is not None and beatmap.stars > filters.max_stars:
        return f"{beatmap.stars:.2f}* is above the maximum of {filters.max_stars}*"
    length = adjusted_length(beatmap.length, mods)
    if filters.max_length is not None and length > filters.max_length:
        return f"length {format_length(length)} is above the maximum of {format_length(filters.max_length)}"
    return None


def build_message(viewer: str, request: Request, beatmap: Beatmap | None) -> str:
    link = f"https://osu.ppy.sh/b/{request.beatmap_id}"
    if beatmap is None:
        parts = [f"[{link} Beatmap #{request.beatmap_id}]"]
    else:
        parts = [
            f"[{link} {beatmap.label}]",
            f"{beatmap.stars:.2f}*",
            format_length(adjusted_length(beatmap.length, request.mods)),
        ]
    if request.mods:
        parts.append("+" + "".join(request.mods))
    message = f"TikTok | {viewer}: " + " ".join(parts)
    if request.note:
        message += f" | {request.note}"
    return message


class RequestBot:
    def __init__(
        self,
        config: Config,
        sender: Sender,
        api: OsuApi | None = None,
        log_path: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.config = config
        self._sender = sender
        self._api = api
        self._log_path = log_path
        self._clock = clock
        self._blocked = {u.strip().lstrip("@").lower() for u in config.blocked_users}
        self._last_request: dict[str, float] = {}
        self._seen: set[int] = set()

    async def handle(self, comment: Comment) -> Outcome:
        request = parse(comment.text, self.config.commands)
        if request is None:
            return Outcome.IGNORED

        viewer = comment.display_name
        user = comment.user_id.lower()
        if user in self._blocked:
            return Outcome.BLOCKED

        now = self._clock()
        last = self._last_request.get(user)
        if last is not None and now - last < self.config.user_cooldown:
            return Outcome.COOLDOWN
        if not self.config.allow_duplicates and request.beatmap_id in self._seen:
            log.info("Skipped %s from %s: already requested this session", request.beatmap_id, viewer)
            return Outcome.DUPLICATE
        self._last_request[user] = now

        beatmap = None
        if self._api is not None:
            try:
                beatmap = await self._api.beatmap(request.beatmap_id, request.mods)
            except ApiError as e:
                self._last_request.pop(user, None)
                log.warning("Could not look up %s for %s: %s", request.beatmap_id, viewer, e)
                return Outcome.ERROR
            if beatmap is None:
                log.info("Skipped %s from %s: beatmap not found", request.beatmap_id, viewer)
                return Outcome.NOT_FOUND
            reason = check_filters(beatmap, request.mods, self.config.filters)
            if reason:
                log.info("Skipped %s from %s: %s", beatmap.label, viewer, reason)
                return Outcome.REJECTED

        if not self.config.allow_duplicates:
            if request.beatmap_id in self._seen:
                return Outcome.DUPLICATE
            self._seen.add(request.beatmap_id)

        message = build_message(viewer, request, beatmap)
        await self._sender.send(self.config.irc_nick, message)
        log.info("Request from %s: %s", viewer, message.split(": ", 1)[1])
        self._write_log(viewer, request, beatmap)
        return Outcome.SENT

    def _write_log(self, viewer: str, request: Request, beatmap: Beatmap | None) -> None:
        if self._log_path is None:
            return
        title = beatmap.label if beatmap else f"Beatmap #{request.beatmap_id}"
        mods = "+" + "".join(request.mods) if request.mods else ""
        line = "\t".join([
            datetime.now().isoformat(timespec="seconds"),
            viewer,
            f"https://osu.ppy.sh/b/{request.beatmap_id}",
            title,
            mods,
            request.note,
        ])
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            log.warning("Could not write %s: %s", self._log_path, e)
