from __future__ import annotations

import asyncio
import getpass
import webbrowser
from pathlib import Path

from . import irc
from .config import Config, save
from .osu_api import ApiError, OsuApi

ACCOUNT_URL = "https://osu.ppy.sh/home/account/edit"


def _ask(prompt: str, current: str = "") -> str:
    suffix = f" [{current}]" if current else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or current


def _ask_secret(prompt: str, current: str = "") -> str:
    suffix = " [press Enter to keep the saved one]" if current else ""
    answer = getpass.getpass(f"{prompt} (hidden while typing){suffix}: ").strip()
    return answer or current


def _yes(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{hint}]: ").strip().lower()
    return default if not answer else answer.startswith("y")


def _ask_number(prompt: str, current, cast):
    shown = "" if current is None else str(current)
    while True:
        answer = input(f"{prompt} [{shown or 'no limit'}] (type 0 for no limit): ").strip()
        if not answer:
            return current
        try:
            value = cast(answer)
        except ValueError:
            print("  Please enter a number.")
            continue
        return None if value == 0 else value


def _open(url: str) -> None:
    if _yes(f"Open {url} in your browser?"):
        webbrowser.open(url)


def _setup_irc(config: Config) -> None:
    print("\nStep 1/3: osu! account")
    print("Requests are sent from your account to yourself, so they show up in your osu! chat.")
    print(f"Get your IRC password at {ACCOUNT_URL} under 'Legacy API' -> 'IRC'.")
    print("It is NOT your normal osu! password.")
    _open(ACCOUNT_URL)
    while True:
        config.osu_username = _ask("osu! username", config.osu_username)
        config.irc_password = _ask_secret("IRC password", config.irc_password)
        if not config.osu_username or not config.irc_password:
            print("  Both are required.")
            continue
        print("Checking login with Bancho...")
        try:
            asyncio.run(irc.verify(config.irc_nick, config.irc_password))
        except irc.AuthError as e:
            print(f"  Login failed: {e}")
            continue
        except (OSError, asyncio.TimeoutError) as e:
            print(f"  Could not reach Bancho: {e or type(e).__name__}")
            if not _yes("Save anyway and continue?", default=False):
                continue
        else:
            print("  Login OK.")
        return


async def _check_api(config: Config) -> None:
    api = OsuApi(config.api_client_id, config.api_client_secret)
    try:
        await api.verify()
    finally:
        await api.close()


def _setup_api(config: Config) -> None:
    print("\nStep 2/3: osu! API (optional, recommended)")
    print("With it, requests show the map title, star rating and length, and filters work.")
    print("Without it, requests are sent as plain beatmap links with no filtering.")
    if not _yes("Set up the osu! API?"):
        config.api_client_id = ""
        config.api_client_secret = ""
        return
    print(f"At {ACCOUNT_URL} go to 'OAuth' -> 'New OAuth Application'.")
    print("Any name works. Use http://localhost as the callback URL.")
    _open(ACCOUNT_URL)
    while True:
        config.api_client_id = _ask("Client ID", config.api_client_id)
        config.api_client_secret = _ask_secret("Client Secret", config.api_client_secret)
        if not config.api_client_id.isdigit() or not config.api_client_secret:
            print("  Client ID must be a number and Client Secret is required.")
            continue
        print("Checking API credentials...")
        try:
            asyncio.run(_check_api(config))
        except ApiError as e:
            print(f"  {e}")
            if _yes("Try again?"):
                continue
            config.api_client_id = ""
            config.api_client_secret = ""
            print("  Continuing without the osu! API.")
        else:
            print("  API OK.")
        return


def _setup_filters(config: Config) -> None:
    print("\nStep 3/3: request rules")
    f = config.filters
    f.min_stars = _ask_number("Minimum star rating", f.min_stars, float)
    f.max_stars = _ask_number("Maximum star rating", f.max_stars, float)
    f.max_length = _ask_number("Maximum length in seconds", f.max_length, int)
    cooldown = _ask_number("Seconds between requests per viewer", config.user_cooldown, int)
    config.user_cooldown = cooldown or 0
    print("More options (modes, ranked status, blocked viewers, commands) are in config.json.")


def run_wizard(path: Path, config: Config | None = None) -> Config:
    config = config or Config()
    print("=" * 60)
    print(" osu! TikTok Request - setup")
    print("=" * 60)
    _setup_irc(config)
    _setup_api(config)
    _setup_filters(config)
    save(config, path)
    print(f"\nSaved to {path}")
    print("Keep this file private. It contains your IRC password.\n")
    return config
