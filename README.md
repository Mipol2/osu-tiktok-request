# osu! TikTok Request

Let your TikTok Live viewers request osu! beatmaps with `!r <beatmap>`. Requests show up in your osu! chat as a clickable map link with title, star rating, length and mods.

It runs on your own PC, uses your own osu! account and reads chat through the [IndoFinity](https://indofinity.com) desktop app. There is no server, so any number of streamers can use it at the same time.

```
TikTok Live chat
      │  "!r 4469665 hddt"
      ▼
IndoFinity desktop app ── ws://localhost:62024 ──▶ osu-tiktok-request
                                                      │  look up the map (osu! API)
                                                      │  check your rules
                                                      ▼
                                          Bancho IRC: your account ──▶ PM to yourself
                                                      ▼
                                   osu! chat:  TikTok | Viewer: Artist - Title [Insane] 6.84* 2:13 +HDDT
```

## Contents

- [osu! TikTok Request](#osu-tiktok-request)
  - [Contents](#contents)
  - [What you need](#what-you-need)
  - [Setup for streamers](#setup-for-streamers)
  - [Usage for viewers](#usage-for-viewers)
  - [Configuration](#configuration)
  - [Testing without going live](#testing-without-going-live)
  - [Troubleshooting](#troubleshooting)
  - [Running from source](#running-from-source)
  - [Building the .exe](#building-the-exe)
  - [Project layout](#project-layout)
  - [Credits](#credits)
  - [License](#license)

## What you need

- Windows PC with the **IndoFinity desktop app**. The browser dashboard does not provide the local websocket.
- An **osu! account** and your **IRC password** from [your account settings](https://osu.ppy.sh/home/account/edit) under *Legacy API → IRC*. This is not your normal login password.
- Optional but recommended: an **osu! OAuth application** (Client ID and Secret) from the same page under *OAuth*. Without it requests still work, but they arrive as plain links and the filters are off.
- osu! **stable**.

## Setup for streamers

1. Download `osu-tiktok-request.exe` from the [latest release](../../releases/latest) and put it in its own folder.
2. Open it. The first run starts a setup wizard:
   1. Enter your osu! username and IRC password. The wizard logs in to Bancho to check them.
   2. Optionally enter your OAuth Client ID and Secret. Use `http://localhost` as the callback URL when you create the application.
   3. Set the request rules: star range, maximum length and the cooldown per viewer.
3. The settings are saved to `config.json` next to the .exe.

Every stream after that:

1. Go live on TikTok.
2. Open the IndoFinity desktop app and press **Connect to Live**.
3. Open `osu-tiktok-request.exe`.
4. In osu!, open the chat. You'll see *"TikTok request bot is running"* from yourself, and requests appear in the same tab.

The app reconnects on its own if IndoFinity or Bancho drops, so you can start it in any order.

> **Keep `config.json` private** and don't show it on stream. It contains your IRC password. If it leaks, generate a new IRC password on the osu! website.

## Usage for viewers

```
!r <beatmap> [mods] [message]
```

| Example | Result |
| --- | --- |
| `!r 4469665` | Requests beatmap 4469665 |
| `!req https://osu.ppy.sh/b/4469665` | Links work too |
| `!request https://osu.ppy.sh/beatmapsets/2101234#osu/4469665` | Including full beatmapset links with a difficulty |
| `!r 4469665 hddt` | With mods. Stars and length are recalculated for DT, HR and similar |
| `!r 4469665 play this with +HR pls` | Mods and a short message can be mixed |

The beatmap ID is the number after `/b/`, `/beatmaps/` or `#osu/` in the map's URL. A beatmapset link without a difficulty (`/beatmapsets/2101234`) is not accepted, because it doesn't say which difficulty to play.

Recognised mods: NF EZ TD HD HR SD PF DT NC HT DC FL RX AP V2.

## Configuration

`config.json` is created by the wizard. Run the app with `--setup` to go through the wizard again, or edit the file directly with Notepad while the app is closed. See [`config.example.json`](config.example.json).

| Key | Default | Description |
| --- | --- | --- |
| `osu_username` | | Your osu! username. Spaces are converted to `_` automatically. |
| `irc_password` | | IRC password from the osu! website. |
| `api_client_id` / `api_client_secret` | | OAuth application credentials. Leave empty to send plain links. |
| `indofinity_url` | `ws://localhost:62024` | IndoFinity's local websocket. |
| `commands` | `["!r", "!req", "!request"]` | Chat commands that count as a request. Not case sensitive. |
| `user_cooldown` | `30` | Seconds a viewer must wait between requests. |
| `allow_duplicates` | `false` | Allow the same map to be requested more than once per session. |
| `send_interval` | `1.5` | Minimum seconds between osu! messages. Must be at least `1.0` to avoid getting silenced by Bancho. |
| `announce_start` | `true` | Send yourself a message when the app starts. |
| `blocked_users` | `[]` | TikTok usernames (`@` optional) whose requests are ignored. |
| `log_file` | `requests.log` | Accepted requests are appended here, tab separated. |
| `filters.min_stars` / `filters.max_stars` | `null` | Star range. `null` means no limit. Modded star rating is used when mods change difficulty. |
| `filters.max_length` | `null` | Maximum drain length in seconds, after DT/HT. |
| `filters.modes` | `["osu"]` | Allowed modes: `osu`, `taiko`, `fruits`, `mania`. Empty list allows all. |
| `filters.statuses` | `[]` | Allowed statuses: `ranked`, `approved`, `qualified`, `loved`, `pending`, `wip`, `graveyard`. Empty list allows all. |

Filters need the osu! API. Without API credentials every valid beatmap ID is forwarded.

## Testing without going live

IndoFinity's **Simulator Panel** can send fake chat events. With the IndoFinity desktop app and this app both running, simulate a chat comment like `!r 4469665`. It should appear in your osu! chat within a couple of seconds.

The console shows why a request was skipped: not found, above the star limit, duplicate and so on. Run with `--verbose` for more detail.

## Troubleshooting

**`Cannot reach IndoFinity at ws://localhost:62024`**
The IndoFinity *desktop app* isn't running, or its websocket is off. Check the Websocket status on IndoFinity's local server page. The browser version is not enough.

**`osu! rejected the IRC login`**
The username or IRC password is wrong. Run with `--setup`. Use the IRC password from *Legacy API*, not your account password.

**Requests show in the console but not in osu!**
Make sure you're logged in to osu! stable with the same account as in `config.json`. The messages come from yourself, so look for a chat tab with your own name.

**Requests arrive as `Beatmap #123` without details**
No osu! API credentials are set, or osu! rejected them at startup. The console says which. Run with `--setup` to add them.

**Silenced in osu!**
Bancho limits how fast an account can send messages. Raise `send_interval` and `user_cooldown`.

**Windows SmartScreen warns about the .exe**
The .exe is not code-signed. Click *More info → Run anyway*, or run from source.

## Running from source

Requires Python 3.11 or newer.

```bash
git clone <this repo>
cd osu-tiktok-request
pip install -r requirements.txt
python run.py
```

Options: `--setup`, `--config PATH`, `--verbose`, `--version`.

Run the tests with:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests use local fake IndoFinity and Bancho servers and a mocked osu! API, so they need no accounts or network access.

## Building the .exe

```bash
pip install -r requirements-dev.txt
pyinstaller --onefile --name osu-tiktok-request run.py
```

The result is `dist/osu-tiktok-request.exe`. Pushing a tag like `v1.0.0` makes GitHub Actions run the tests, build the .exe on Windows and attach it to a release.

## Project layout

```
osureq/
  __main__.py     command line entry point, wires everything together
  wizard.py       first-run setup
  config.py       config.json loading, saving and validation
  indofinity.py   IndoFinity websocket client, chat event parsing
  commands.py     !r command, beatmap ID, link and mod parsing
  osu_api.py      osu! API v2 client, beatmap lookups and modded star rating
  irc.py          Bancho IRC client with rate-limited send queue and reconnects
  bot.py          request handling: cooldowns, duplicates, filters, message format
tests/            unit and integration tests
run.py            entry point for running from source and for PyInstaller
```

## Credits

- Inspired by [osu-beatmap-request-module](https://github.com/MineFrostID/osu-beatmap-request-module) by MineFrostID, which does the same for YouTube and Twitch through Streamer.bot.
- Chat events come from [IndoFinity](https://indofinity.com), whose event data follows [TikTok-Live-Connector](https://github.com/zerodytrash/TikTok-Live-Connector).

Not affiliated with TikTok, IndoFinity or ppy.

## License

[MIT](LICENSE)
