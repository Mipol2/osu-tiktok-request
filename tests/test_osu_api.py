import asyncio
import json

import httpx
import pytest

from osureq.osu_api import ApiError, OsuApi, adjusted_length

BEATMAP = {
    "id": 100,
    "beatmapset_id": 10,
    "version": "Insane",
    "mode": "osu",
    "status": "ranked",
    "difficulty_rating": 5.12,
    "total_length": 150,
    "beatmapset": {"artist": "Artist", "title": "Song"},
}


def make_api(handler):
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OsuApi("123", "secret", http=http, base_url="https://osu.test")


def default_handler(calls):
    def handler(request: httpx.Request):
        calls.append(request)
        if request.url.path == "/oauth/token":
            body = json.loads(request.content)
            if body["client_secret"] != "secret":
                return httpx.Response(401)
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 86400})
        if request.url.path == "/api/v2/beatmaps/100":
            return httpx.Response(200, json=BEATMAP)
        if request.url.path == "/api/v2/beatmaps/100/attributes":
            assert json.loads(request.content) == {"mods": ["DT"], "ruleset": "osu"}
            return httpx.Response(200, json={"attributes": {"star_rating": 7.25}})
        return httpx.Response(404)

    return handler


def test_beatmap_lookup_reuses_token():
    calls = []

    async def scenario():
        api = make_api(default_handler(calls))
        first = await api.beatmap(100)
        await api.beatmap(100)
        await api.close()
        return first

    beatmap = asyncio.run(scenario())
    assert beatmap.label == "Artist - Song [Insane]"
    assert beatmap.stars == 5.12
    assert [c.url.path for c in calls].count("/oauth/token") == 1
    assert calls[1].headers["Authorization"] == "Bearer tok"


def test_missing_beatmap_returns_none():
    assert asyncio.run(make_api(default_handler([])).beatmap(999)) is None


def test_modded_star_rating():
    beatmap = asyncio.run(make_api(default_handler([])).beatmap(100, ("DT",)))
    assert beatmap.stars == 7.25


def test_hidden_does_not_request_attributes():
    calls = []
    asyncio.run(make_api(default_handler(calls)).beatmap(100, ("HD",)))
    assert not any(c.url.path.endswith("/attributes") for c in calls)


def test_bad_credentials():
    http = httpx.AsyncClient(transport=httpx.MockTransport(default_handler([])))
    api = OsuApi("123", "wrong", http=http, base_url="https://osu.test")
    with pytest.raises(ApiError):
        asyncio.run(api.verify())


def test_server_error_raises():
    def handler(request):
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        return httpx.Response(500)

    with pytest.raises(ApiError):
        asyncio.run(make_api(handler).beatmap(100))


def test_expired_token_is_refreshed_once():
    tokens = iter(["old", "new"])
    seen = []

    def handler(request):
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": next(tokens), "expires_in": 3600})
        seen.append(request.headers["Authorization"])
        if request.headers["Authorization"] == "Bearer old":
            return httpx.Response(401)
        return httpx.Response(200, json=BEATMAP)

    assert asyncio.run(make_api(handler).beatmap(100)) is not None
    assert seen == ["Bearer old", "Bearer new"]


def test_adjusted_length():
    assert adjusted_length(180, ()) == 180
    assert adjusted_length(180, ("DT",)) == 120
    assert adjusted_length(180, ("NC", "HD")) == 120
    assert adjusted_length(180, ("HT",)) == 240
