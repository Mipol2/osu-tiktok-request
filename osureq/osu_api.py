from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable

import httpx

BASE_URL = "https://osu.ppy.sh"
SPEED_UP = frozenset({"DT", "NC"})
SLOW_DOWN = frozenset({"HT", "DC"})
DIFFICULTY_MODS = frozenset({"EZ", "HR", "DT", "NC", "HT", "DC", "FL", "TD"})


class ApiError(Exception):
    pass


@dataclass(frozen=True)
class Beatmap:
    id: int
    set_id: int
    artist: str
    title: str
    version: str
    mode: str
    status: str
    stars: float
    length: int

    @property
    def label(self) -> str:
        return f"{self.artist} - {self.title} [{self.version}]"


def adjusted_length(length: int, mods: Iterable[str]) -> int:
    mods = set(mods)
    if mods & SPEED_UP:
        return round(length / 1.5)
    if mods & SLOW_DOWN:
        return round(length / 0.75)
    return length


class OsuApi:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        http: httpx.AsyncClient | None = None,
        base_url: str = BASE_URL,
    ):
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._http = http or httpx.AsyncClient(timeout=10)
        self._base = base_url.rstrip("/")
        self._token: str | None = None
        self._expires = 0.0

    async def close(self) -> None:
        await self._http.aclose()

    async def verify(self) -> None:
        self._token = None
        await self._ensure_token()

    async def _ensure_token(self) -> str:
        if self._token and time.monotonic() < self._expires - 60:
            return self._token
        try:
            response = await self._http.post(
                f"{self._base}/oauth/token",
                json={
                    "client_id": int(self._client_id),
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                    "scope": "public",
                },
            )
        except ValueError as e:
            raise ApiError("client id must be a number") from e
        except httpx.HTTPError as e:
            raise ApiError(f"could not reach osu!: {e}") from e
        if response.status_code in (400, 401):
            raise ApiError("osu! rejected the API client id or secret")
        if response.status_code >= 400:
            raise ApiError(f"token request failed with HTTP {response.status_code}")
        data = response.json()
        self._token = data["access_token"]
        self._expires = time.monotonic() + float(data.get("expires_in", 3600))
        return self._token

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        for attempt in range(2):
            token = await self._ensure_token()
            try:
                response = await self._http.request(
                    method,
                    f"{self._base}/api/v2{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    **kwargs,
                )
            except httpx.HTTPError as e:
                raise ApiError(f"could not reach osu!: {e}") from e
            if response.status_code == 401 and attempt == 0:
                self._token = None
                continue
            return response
        raise ApiError("osu! API authorization failed")

    async def beatmap(self, beatmap_id: int, mods: Iterable[str] = ()) -> Beatmap | None:
        mods = tuple(mods)
        response = await self._request("GET", f"/beatmaps/{beatmap_id}")
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise ApiError(f"beatmap lookup failed with HTTP {response.status_code}")

        data = response.json()
        beatmapset = data["beatmapset"]
        stars = float(data["difficulty_rating"])
        if DIFFICULTY_MODS & set(mods):
            stars = await self._modded_stars(beatmap_id, data["mode"], mods) or stars

        return Beatmap(
            id=int(data["id"]),
            set_id=int(data["beatmapset_id"]),
            artist=beatmapset["artist"],
            title=beatmapset["title"],
            version=data["version"],
            mode=data["mode"],
            status=data["status"],
            stars=stars,
            length=int(data["total_length"]),
        )

    async def _modded_stars(self, beatmap_id: int, mode: str, mods: tuple[str, ...]) -> float | None:
        try:
            response = await self._request(
                "POST",
                f"/beatmaps/{beatmap_id}/attributes",
                json={"mods": list(mods), "ruleset": mode},
            )
            if response.status_code >= 400:
                return None
            return float(response.json()["attributes"]["star_rating"])
        except (ApiError, KeyError, TypeError, ValueError):
            return None
