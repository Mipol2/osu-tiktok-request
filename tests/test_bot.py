import asyncio

from osureq.bot import Outcome, RequestBot, build_message, check_filters
from osureq.commands import Request
from osureq.config import Config, Filters
from osureq.indofinity import Comment
from osureq.osu_api import ApiError, Beatmap

MAP = Beatmap(
    id=100, set_id=10, artist="Artist", title="Song", version="Insane",
    mode="osu", status="ranked", stars=5.0, length=180,
)


class FakeSender:
    def __init__(self):
        self.sent = []

    async def send(self, target, text):
        self.sent.append((target, text))


class FakeApi:
    def __init__(self, beatmaps=None, error=None):
        self.beatmaps = beatmaps or {}
        self.error = error
        self.calls = 0

    async def beatmap(self, beatmap_id, mods=()):
        self.calls += 1
        if self.error:
            raise self.error
        return self.beatmaps.get(beatmap_id)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def make_bot(api=None, **overrides):
    config = Config(osu_username="My Name", irc_password="x", **overrides)
    sender, clock = FakeSender(), Clock()
    return RequestBot(config, sender, api, clock=clock), sender, clock


def comment(text, user="viewer", nickname="Viewer"):
    return Comment(user, nickname, text)


def handle(bot, text, **kwargs):
    return asyncio.run(bot.handle(comment(text, **kwargs)))


def test_sends_to_own_nick_with_details():
    bot, sender, _ = make_bot(FakeApi({100: MAP}))
    assert handle(bot, "!r 100 hd nice map") is Outcome.SENT
    target, text = sender.sent[0]
    assert target == "My_Name"
    assert text == "TikTok | Viewer: [https://osu.ppy.sh/b/100 Artist - Song [Insane]] 5.00* 3:00 +HD | nice map"


def test_without_api_sends_plain_link():
    bot, sender, _ = make_bot()
    assert handle(bot, "!r 555") is Outcome.SENT
    assert sender.sent[0][1] == "TikTok | Viewer: [https://osu.ppy.sh/b/555 Beatmap #555]"


def test_ignores_chat():
    bot, sender, _ = make_bot()
    assert handle(bot, "hello") is Outcome.IGNORED
    assert not sender.sent


def test_cooldown_per_viewer():
    bot, sender, clock = make_bot(user_cooldown=30)
    assert handle(bot, "!r 1") is Outcome.SENT
    assert handle(bot, "!r 2") is Outcome.COOLDOWN
    assert handle(bot, "!r 3", user="other") is Outcome.SENT
    clock.now += 31
    assert handle(bot, "!r 4") is Outcome.SENT
    assert len(sender.sent) == 3


def test_duplicates_blocked_by_default():
    bot, _, _ = make_bot(user_cooldown=0)
    assert handle(bot, "!r 1") is Outcome.SENT
    assert handle(bot, "!r 1", user="other") is Outcome.DUPLICATE


def test_duplicates_allowed():
    bot, _, _ = make_bot(user_cooldown=0, allow_duplicates=True)
    assert handle(bot, "!r 1") is Outcome.SENT
    assert handle(bot, "!r 1") is Outcome.SENT


def test_blocked_users():
    bot, sender, _ = make_bot(blocked_users=["@Spammer"])
    assert handle(bot, "!r 1", user="spammer") is Outcome.BLOCKED
    assert not sender.sent


def test_not_found_and_filters():
    api = FakeApi({100: MAP})
    bot, sender, _ = make_bot(api, user_cooldown=0, filters=Filters(max_stars=4.0))
    assert handle(bot, "!r 999") is Outcome.NOT_FOUND
    assert handle(bot, "!r 100") is Outcome.REJECTED
    assert not sender.sent


def test_api_error_releases_cooldown():
    bot, _, _ = make_bot(FakeApi(error=ApiError("down")), user_cooldown=60)
    assert handle(bot, "!r 100") is Outcome.ERROR
    bot._api = FakeApi({100: MAP})
    assert handle(bot, "!r 100") is Outcome.SENT


def test_concurrent_duplicate_requests_send_once():
    bot, sender, _ = make_bot(FakeApi({100: MAP}), user_cooldown=0)

    async def both():
        return await asyncio.gather(
            bot.handle(comment("!r 100", user="a")),
            bot.handle(comment("!r 100", user="b")),
        )

    outcomes = asyncio.run(both())
    assert sorted(outcomes) == sorted([Outcome.SENT, Outcome.DUPLICATE])
    assert len(sender.sent) == 1


def test_check_filters():
    assert check_filters(MAP, (), Filters()) is None
    assert "mode" in check_filters(MAP, (), Filters(modes=["mania"]))
    assert "status" in check_filters(MAP, (), Filters(statuses=["loved"]))
    assert "minimum" in check_filters(MAP, (), Filters(min_stars=6))
    assert "length" in check_filters(MAP, (), Filters(max_length=120))
    assert check_filters(MAP, ("DT",), Filters(max_length=120)) is None


def test_message_shows_modded_length():
    message = build_message("V", Request(100, ("DT",)), MAP)
    assert " 2:00 +DT" in message


def test_writes_log(tmp_path):
    path = tmp_path / "requests.log"
    config = Config(osu_username="me", irc_password="x")
    bot = RequestBot(config, FakeSender(), FakeApi({100: MAP}), log_path=path)
    asyncio.run(bot.handle(comment("!r 100 +HD")))
    line = path.read_text(encoding="utf-8").strip().split("\t")
    assert line[1:5] == ["Viewer", "https://osu.ppy.sh/b/100", "Artist - Song [Insane]", "+HD"]
