import asyncio

import pytest

from osureq.irc import AuthError, BanchoIRC, truncate, verify


class FakeBancho:
    def __init__(self, password="secret"):
        self.password = password
        self.received: list[str] = []
        self.logins = 0
        self.server = None
        self.port = None

    async def __aenter__(self):
        self.server = await asyncio.start_server(self._client, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *exc):
        self.server.close()
        await self.server.wait_closed()

    async def _client(self, reader, writer):
        password = None
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    return
                line = raw.decode().rstrip("\r\n")
                self.received.append(line)
                if line.startswith("PASS "):
                    password = line[5:]
                elif line.startswith("NICK "):
                    nick = line[5:]
                    if password != self.password:
                        writer.write(b":cho.ppy.sh 464 :Bad authentication token.\r\n")
                        await writer.drain()
                        writer.close()
                        return
                    self.logins += 1
                    writer.write(f":cho.ppy.sh 001 {nick} :Welcome\r\nPING cho.ppy.sh\r\n".encode())
                    await writer.drain()
        except ConnectionError:
            pass

    def privmsgs(self):
        return [line for line in self.received if line.startswith("PRIVMSG")]


async def wait_for(predicate, timeout=3):
    async def loop():
        while not predicate():
            await asyncio.sleep(0.01)

    await asyncio.wait_for(loop(), timeout)


def test_truncate():
    assert truncate("a\r\nb") == "a  b"
    long = "é" * 300
    assert len(truncate(long).encode()) <= 400


def test_verify_ok_and_bad_password():
    async def scenario():
        async with FakeBancho() as server:
            await verify("me", "secret", "127.0.0.1", server.port)
            with pytest.raises(AuthError):
                await verify("me", "wrong", "127.0.0.1", server.port)

    asyncio.run(scenario())


def test_sends_queued_messages_and_answers_ping():
    async def scenario():
        async with FakeBancho() as server:
            client = BanchoIRC("me", "secret", send_interval=0.01, host="127.0.0.1", port=server.port)
            await client.send("me", "first")
            await client.send("me", "second")
            task = asyncio.create_task(client.run())
            await wait_for(lambda: len(server.privmsgs()) == 2)
            await wait_for(lambda: any(line.startswith("PONG") for line in server.received))
            task.cancel()
            assert server.privmsgs() == ["PRIVMSG me :first", "PRIVMSG me :second"]

    asyncio.run(scenario())


def test_run_raises_on_bad_password():
    async def scenario():
        async with FakeBancho() as server:
            client = BanchoIRC("me", "wrong", host="127.0.0.1", port=server.port)
            with pytest.raises(AuthError):
                await asyncio.wait_for(client.run(), 3)

    asyncio.run(scenario())
