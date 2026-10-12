import asyncio
import functools
import json

from websockets.asyncio.server import serve

import osureq.__main__ as app
from osureq.config import Config, save
from test_irc import FakeBancho, wait_for


def chat(user, text):
    return json.dumps({"event": "chat", "data": {"uniqueId": user, "nickname": user.upper(), "comment": text}})


def test_end_to_end(tmp_path, monkeypatch):
    async def scenario():
        async def indofinity(ws):
            await ws.send(chat("a", "hello"))
            await ws.send(chat("a", "!r 4469665 hddt gl"))
            await ws.send(chat("b", "!req https://osu.ppy.sh/b/123"))
            await ws.send(chat("c", "!r 4469665"))
            await asyncio.sleep(5)

        async with FakeBancho("pw") as bancho, serve(indofinity, "127.0.0.1", 0) as ws:
            monkeypatch.setattr(app, "BanchoIRC", functools.partial(app.BanchoIRC, host="127.0.0.1", port=bancho.port))
            config = Config(
                osu_username="Test User",
                irc_password="pw",
                indofinity_url=f"ws://127.0.0.1:{ws.sockets[0].getsockname()[1]}",
                send_interval=1.0,
            )
            task = asyncio.create_task(app.run(config, tmp_path))
            await wait_for(lambda: len(bancho.privmsgs()) >= 3, 8)
            await asyncio.sleep(1.2)
            task.cancel()
            return bancho.privmsgs()

    sent = asyncio.run(scenario())
    assert sent == [
        "PRIVMSG Test_User :TikTok request bot is running. Requests will appear here.",
        "PRIVMSG Test_User :TikTok | A: [https://osu.ppy.sh/b/4469665 Beatmap #4469665] +HDDT | gl",
        "PRIVMSG Test_User :TikTok | B: [https://osu.ppy.sh/b/123 Beatmap #123]",
    ]
    assert len((tmp_path / "requests.log").read_text(encoding="utf-8").splitlines()) == 2


def test_bad_password_exits_with_error(tmp_path, monkeypatch):
    async def scenario():
        async with FakeBancho("pw") as bancho:
            monkeypatch.setattr(app, "BanchoIRC", functools.partial(app.BanchoIRC, host="127.0.0.1", port=bancho.port))
            config = Config(osu_username="me", irc_password="wrong", indofinity_url="ws://127.0.0.1:1", announce_start=False)
            return await asyncio.wait_for(app.run(config, tmp_path), 5)

    assert asyncio.run(scenario()) == 1


def test_main_rejects_invalid_config(tmp_path, capsys):
    path = tmp_path / "config.json"
    save(Config(osu_username="me", irc_password="pw", send_interval=0.1), path)
    assert app.main(["--config", str(path)]) == 1
    assert "send_interval" in capsys.readouterr().out
