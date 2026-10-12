from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

MODS = frozenset({"NF", "EZ", "TD", "HD", "HR", "SD", "PF", "DT", "NC", "HT", "DC", "FL", "RX", "AP", "V2"})
MAX_NOTE = 80

_ID = re.compile(r"[0-9]{1,10}")
_LINK = re.compile(
    r"(?:https?://)?osu\.ppy\.sh/(?:b|beatmaps)/([0-9]{1,10})"
    r"|(?:https?://)?osu\.ppy\.sh/beatmapsets/[0-9]+#[a-z]+/([0-9]{1,10})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Request:
    beatmap_id: int
    mods: tuple[str, ...] = ()
    note: str = ""


def parse_beatmap_id(token: str) -> int | None:
    if _ID.fullmatch(token):
        value = int(token)
        return value or None
    match = _LINK.fullmatch(token.split("?")[0])
    if match:
        return int(match.group(1) or match.group(2))
    return None


def parse_mods(token: str) -> tuple[str, ...] | None:
    text = token.lstrip("+").upper()
    if not text or len(text) % 2:
        return None
    chunks = tuple(text[i:i + 2] for i in range(0, len(text), 2))
    return chunks if all(c in MODS for c in chunks) else None


def parse(comment: str, commands: Iterable[str]) -> Request | None:
    parts = comment.split()
    if len(parts) < 2 or parts[0].lower() not in {c.lower() for c in commands}:
        return None
    beatmap_id = parse_beatmap_id(parts[1])
    if beatmap_id is None:
        return None

    mods: list[str] = []
    words: list[str] = []
    for token in parts[2:]:
        found = parse_mods(token)
        if found is None:
            words.append(token)
            continue
        for mod in found:
            if mod not in mods:
                mods.append(mod)

    note = " ".join(words)[:MAX_NOTE].strip()
    return Request(beatmap_id, tuple(mods), note)
