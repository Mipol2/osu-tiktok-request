from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

CONFIG_NAME = "config.json"
MODES = ("osu", "taiko", "fruits", "mania")
STATUSES = ("ranked", "approved", "qualified", "loved", "pending", "wip", "graveyard")
MIN_SEND_INTERVAL = 1.0


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


@dataclass
class Filters:
    min_stars: float | None = None
    max_stars: float | None = None
    max_length: int | None = None
    modes: list[str] = field(default_factory=lambda: ["osu"])
    statuses: list[str] = field(default_factory=list)


@dataclass
class Config:
    osu_username: str = ""
    irc_password: str = ""
    api_client_id: str = ""
    api_client_secret: str = ""
    indofinity_url: str = "ws://localhost:62024"
    commands: list[str] = field(default_factory=lambda: ["!r", "!req", "!request"])
    user_cooldown: int = 30
    allow_duplicates: bool = False
    send_interval: float = 1.5
    announce_start: bool = True
    blocked_users: list[str] = field(default_factory=list)
    log_file: str = "requests.log"
    filters: Filters = field(default_factory=Filters)

    @property
    def irc_nick(self) -> str:
        return self.osu_username.strip().replace(" ", "_")

    @property
    def has_api(self) -> bool:
        return bool(self.api_client_id.strip() and self.api_client_secret.strip())

    def validate(self) -> list[str]:
        errors = []
        if not self.osu_username.strip():
            errors.append("osu_username is empty")
        if not self.irc_password.strip():
            errors.append("irc_password is empty")
        if not self.commands:
            errors.append("commands must contain at least one command")
        if self.send_interval < MIN_SEND_INTERVAL:
            errors.append(f"send_interval must be at least {MIN_SEND_INTERVAL}")
        if self.user_cooldown < 0:
            errors.append("user_cooldown cannot be negative")
        if self.api_client_id.strip() and not self.api_client_id.strip().isdigit():
            errors.append("api_client_id must be a number")
        f = self.filters
        if f.min_stars is not None and f.max_stars is not None and f.min_stars > f.max_stars:
            errors.append("filters.min_stars is greater than filters.max_stars")
        bad_modes = [m for m in f.modes if m not in MODES]
        if bad_modes:
            errors.append(f"unknown modes {bad_modes}, use any of {list(MODES)}")
        bad_statuses = [s for s in f.statuses if s not in STATUSES]
        if bad_statuses:
            errors.append(f"unknown statuses {bad_statuses}, use any of {list(STATUSES)}")
        return errors


def _known(cls, data: dict) -> dict:
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in names}


def load(path: Path) -> Config:
    data = json.loads(path.read_text(encoding="utf-8"))
    filters = Filters(**_known(Filters, data.pop("filters", None) or {}))
    return Config(**_known(Config, data), filters=filters)


def save(config: Config, path: Path) -> None:
    path.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
