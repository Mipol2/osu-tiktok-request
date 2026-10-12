from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from . import __version__, indofinity
from .bot import RequestBot
from .config import CONFIG_NAME, Config, app_dir, load
from .irc import AuthError, BanchoIRC
from .osu_api import ApiError, OsuApi
from .wizard import run_wizard

log = logging.getLogger("osureq")


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("osureq").setLevel(logging.DEBUG if verbose else logging.INFO)
    for noisy in ("httpx", "httpcore", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def _safe_handle(bot: RequestBot, comment: indofinity.Comment) -> None:
    try:
        await bot.handle(comment)
    except Exception:
        log.exception("Unexpected error while handling a request from %s", comment.display_name)


async def run(config: Config, base_dir: Path) -> int:
    api = None
    if config.has_api:
        api = OsuApi(config.api_client_id, config.api_client_secret)
        try:
            await api.verify()
        except ApiError as e:
            log.warning("osu! API unavailable (%s). Requests will be sent as plain links.", e)
            await api.close()
            api = None
    else:
        log.warning("No osu! API credentials: requests are sent as plain links and filters are off.")

    irc = BanchoIRC(config.irc_nick, config.irc_password, config.send_interval)
    bot = RequestBot(config, irc, api, log_path=base_dir / config.log_file)

    if config.announce_start:
        await irc.send(config.irc_nick, "TikTok request bot is running. Requests will appear here.")

    async def consume() -> None:
        tasks: set[asyncio.Task] = set()
        async for comment in indofinity.comments(config.indofinity_url):
            task = asyncio.create_task(_safe_handle(bot, comment))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    log.info("Listening for %s in TikTok chat", ", ".join(f"{c} <beatmap>" for c in config.commands))
    exit_code = 0
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(irc.run())
            group.create_task(consume())
    except* AuthError:
        log.error("osu! rejected the IRC login. Run the app with --setup to re-enter your username and IRC password.")
        exit_code = 1
    finally:
        if api is not None:
            await api.close()
    return exit_code


def _pause_if_frozen() -> None:
    if getattr(sys, "frozen", False):
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="osu-tiktok-request", description="osu! beatmap requests from TikTok Live via IndoFinity")
    parser.add_argument("--setup", action="store_true", help="run the setup wizard again")
    parser.add_argument("--config", type=Path, help=f"path to the config file (default: {CONFIG_NAME} next to the app)")
    parser.add_argument("--verbose", action="store_true", help="show debug logs")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    path = args.config or app_dir() / CONFIG_NAME

    try:
        existing = load(path) if path.exists() else None
    except (OSError, ValueError, TypeError) as e:
        print(f"Could not read {path}: {e}")
        _pause_if_frozen()
        return 1

    try:
        if args.setup or existing is None:
            config = run_wizard(path, existing)
        else:
            config = existing
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.")
        return 1

    errors = config.validate()
    if errors:
        print(f"Problems in {path}:")
        for error in errors:
            print(f"  - {error}")
        print("Fix them in the file or run the app with --setup.")
        _pause_if_frozen()
        return 1

    print(f"osu! TikTok Request {__version__}  |  sending to {config.irc_nick}  |  Ctrl+C to stop\n")
    try:
        code = asyncio.run(run(config, path.parent))
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    if code:
        _pause_if_frozen()
    return code


if __name__ == "__main__":
    sys.exit(main())
