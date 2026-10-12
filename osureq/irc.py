from __future__ import annotations

import asyncio
import logging

HOST = "irc.ppy.sh"
PORT = 6667
MAX_MESSAGE_BYTES = 400
READ_TIMEOUT = 300

log = logging.getLogger("osureq.irc")


class AuthError(Exception):
    pass


def truncate(text: str, limit: int = MAX_MESSAGE_BYTES) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    data = text.encode("utf-8")
    if len(data) <= limit:
        return text
    return data[:limit].decode("utf-8", "ignore")


def _login_lines(nick: str, password: str) -> bytes:
    return f"PASS {password}\r\nNICK {nick}\r\nUSER {nick} 0 * :{nick}\r\n".encode()


def _numeric(line: str) -> str | None:
    parts = line.split(" ", 2)
    return parts[1] if len(parts) > 1 and parts[1].isdigit() else None


async def verify(nick: str, password: str, host: str = HOST, port: int = PORT, timeout: float = 20) -> None:
    async def attempt() -> None:
        reader, writer = await asyncio.open_connection(host, port)
        try:
            writer.write(_login_lines(nick, password))
            await writer.drain()
            while True:
                raw = await reader.readline()
                if not raw:
                    raise AuthError("connection closed during login")
                code = _numeric(raw.decode("utf-8", "replace").strip())
                if code == "001":
                    return
                if code == "464":
                    raise AuthError("wrong username or IRC password")
        finally:
            writer.close()

    await asyncio.wait_for(attempt(), timeout)


class BanchoIRC:
    def __init__(
        self,
        nick: str,
        password: str,
        send_interval: float = 1.5,
        host: str = HOST,
        port: int = PORT,
    ):
        self.nick = nick
        self._password = password
        self._interval = send_interval
        self._host = host
        self._port = port
        self._queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self._retry: tuple[str, str] | None = None
        self.ready = asyncio.Event()

    async def send(self, target: str, text: str) -> None:
        await self._queue.put((target, truncate(text)))

    async def run(self) -> None:
        delay = 2.0
        while True:
            try:
                await self._session()
                reason = "closed by server"
            except AuthError:
                raise
            except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
                reason = str(e) or type(e).__name__
            if self.ready.is_set():
                delay = 2.0
            self.ready.clear()
            log.warning("Bancho connection lost (%s), reconnecting in %.0fs", reason, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    async def _session(self) -> None:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        sender: asyncio.Task | None = None
        try:
            writer.write(_login_lines(self.nick, self._password))
            await writer.drain()
            while True:
                raw = await asyncio.wait_for(reader.readline(), READ_TIMEOUT)
                if not raw:
                    return
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                if line.startswith("PING"):
                    writer.write(f"PONG {line[5:]}\r\n".encode())
                    await writer.drain()
                    continue
                code = _numeric(line)
                if code == "464":
                    raise AuthError("wrong username or IRC password")
                if code == "001" and sender is None:
                    log.info("Logged in to Bancho as %s", self.nick)
                    self.ready.set()
                    sender = asyncio.create_task(self._sender(writer))
                if sender is not None and sender.done() and not sender.cancelled():
                    error = sender.exception()
                    if error:
                        raise error
        finally:
            if sender is not None:
                sender.cancel()
            writer.close()

    async def _sender(self, writer: asyncio.StreamWriter) -> None:
        while True:
            if self._retry is None:
                self._retry = await self._queue.get()
            target, text = self._retry
            writer.write(f"PRIVMSG {target} :{text}\r\n".encode("utf-8"))
            await writer.drain()
            self._retry = None
            await asyncio.sleep(self._interval)
