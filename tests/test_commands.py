import pytest

from osureq.commands import Request, parse, parse_beatmap_id, parse_mods

COMMANDS = ["!r", "!req", "!request"]


@pytest.mark.parametrize(
    "token, expected",
    [
        ("4469665", 4469665),
        ("https://osu.ppy.sh/b/4469665", 4469665),
        ("osu.ppy.sh/beatmaps/4469665", 4469665),
        ("https://osu.ppy.sh/beatmapsets/2101234#osu/4469665", 4469665),
        ("https://osu.ppy.sh/beatmaps/4469665?mode=osu", 4469665),
        ("https://osu.ppy.sh/beatmapsets/2101234", None),
        ("0", None),
        ("abc", None),
        ("١٢٣", None),
        ("12345678901", None),
    ],
)
def test_parse_beatmap_id(token, expected):
    assert parse_beatmap_id(token) == expected


@pytest.mark.parametrize(
    "token, expected",
    [
        ("hddt", ("HD", "DT")),
        ("+HR", ("HR",)),
        ("HDHRFL", ("HD", "HR", "FL")),
        ("so", None),
        ("this", None),
        ("hdd", None),
        ("+", None),
    ],
)
def test_parse_mods(token, expected):
    assert parse_mods(token) == expected


def test_basic_request():
    assert parse("!r 4469665", COMMANDS) == Request(4469665)


def test_aliases_are_case_insensitive():
    assert parse("!REQ 123", COMMANDS) == Request(123)
    assert parse("!Request 123", COMMANDS) == Request(123)


def test_mods_and_note():
    assert parse("!r 123 play this with hrhd pls", COMMANDS) == Request(123, ("HR", "HD"), "play this with pls")


def test_duplicate_mods_are_merged():
    assert parse("!r 123 hd +HD dt", COMMANDS) == Request(123, ("HD", "DT"))


def test_note_is_truncated():
    request = parse("!r 123 " + "word " * 50, COMMANDS)
    assert len(request.note) <= 80


@pytest.mark.parametrize("text", ["hello", "!r", "!r abc", "!rr 123", "r! 123", "", "!r 0"])
def test_non_requests(text):
    assert parse(text, COMMANDS) is None
