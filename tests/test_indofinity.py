import asyncio
import json

from websockets.asyncio.server import serve

from osureq.indofinity import Comment, comments, parse_event


def chat(**data):
    return json.dumps({"event": "chat", "data": data})


def test_parse_flat_chat_event():
    assert parse_event(chat(uniqueId="u1", nickname="Nick", comment="!r 1")) == Comment("u1", "Nick", "!r 1")


def test_parse_nested_user():
    raw = chat(user={"uniqueId": "u2", "nickname": "N2"}, comment="hi")
    assert parse_event(raw) == Comment("u2", "N2", "hi")


def test_ignores_other_events_and_garbage():
    assert parse_event(json.dumps({"event": "gift", "data": {}})) is None
    assert parse_event("not json") is None
    assert parse_event(json.dumps([1, 2])) is None
    assert parse_event(chat(uniqueId="u1", comment="")) is None
    assert parse_event(json.dumps({"event": "chat", "data": "x"})) is None


def test_display_name_falls_back_to_user_id():
    assert Comment("u1", " ", "x").display_name == "u1"


def test_streams_comments_from_websocket():
    async def scenario():
        async def handler(ws):
            await ws.send(json.dumps({"event": "like", "data": {}}))
            await ws.send(chat(uniqueId="a", nickname="A", comment="!r 1"))
            await ws.send(chat(uniqueId="b", nickname="B", comment="!r 2"))
            await asyncio.sleep(1)

        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            received = []
            async for comment in comments(f"ws://127.0.0.1:{port}"):
                received.append(comment.text)
                if len(received) == 2:
                    break
            assert received == ["!r 1", "!r 2"]

    asyncio.run(asyncio.wait_for(scenario(), 5))
