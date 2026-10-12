import json

from osureq.config import Config, Filters, load, save


def test_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    config = Config(osu_username="My Name", irc_password="pw", filters=Filters(max_stars=6.5))
    save(config, path)
    assert load(path) == config


def test_unknown_keys_are_ignored_and_defaults_filled(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"osu_username": "me", "old_option": 1, "filters": {"max_length": 300, "x": 2}}))
    config = load(path)
    assert config.osu_username == "me"
    assert config.filters.max_length == 300
    assert config.filters.modes == ["osu"]
    assert config.commands == ["!r", "!req", "!request"]


def test_irc_nick_replaces_spaces():
    assert Config(osu_username=" My Name ").irc_nick == "My_Name"


def test_validate():
    assert Config(osu_username="me", irc_password="pw").validate() == []
    errors = Config(
        send_interval=0.2,
        api_client_id="abc",
        filters=Filters(min_stars=6, max_stars=5, modes=["std"], statuses=["unranked"]),
    ).validate()
    assert len(errors) == 7
