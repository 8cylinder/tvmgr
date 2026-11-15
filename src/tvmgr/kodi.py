"""Kodi JSON-RPC helpers."""

from __future__ import annotations

import json
from typing import Any, cast

import requests

from .config import Config

WATCHED_MEDIA = {
    "tv": (
        "VideoLibrary.GetEpisodes",
        "showtitle",
        "episodes",
        "showtitle",
    ),
    "movies": (
        "VideoLibrary.GetMovies",
        "originaltitle",
        "movies",
        "originaltitle",
    ),
}


class KodiError(Exception):
    """Raised when Kodi cannot be reached or returns an unusable response."""


def get_watched_media(
    ip_address: str,
    is_tv: bool,
    config: Config,
) -> list[tuple[str, str]]:
    """Return watched (file, title) pairs from a Kodi device."""
    endpoint = f"http://{ip_address}:{config.kodi.port}/jsonrpc"
    media_type = "tv" if is_tv else "movies"
    method, title_property, result_key, title_key = WATCHED_MEDIA[media_type]

    kodi_data = {
        "jsonrpc": "2.0",
        "method": method,
        "params": {
            "properties": [title_property, "file"],
            "filter": {
                "field": "playcount",
                "operator": "greaterthan",
                "value": "0",
            },
        },
        "id": "get-watched-episodes",
    }
    payload = {"request": json.dumps(kodi_data)}

    try:
        response = requests.get(endpoint, payload)
    except requests.exceptions.ConnectionError as exc:
        raise KodiError(f"network is unreachable: {endpoint}") from exc

    try:
        result = response.json()
        episodes = result["result"][result_key]
        return [(item["file"], item[title_key]) for item in episodes]
    except (ValueError, KeyError, TypeError) as exc:
        raise KodiError(f"unexpected response from {endpoint}: {exc}") from exc


def get_kodi_info(ip: str, config: Config) -> dict[str, Any]:
    """Gather comprehensive information about a Kodi device."""
    info: dict[str, Any] = {
        "ip": ip,
        "url": f"http://{ip}:{config.kodi.port}",
        "system": {},
        "library": {},
        "player": {},
        "addons": {},
    }

    try:
        system_props = _query_kodi(
            config,
            ip,
            "System.GetProperties",
            {
                "properties": [
                    "canshutdown",
                    "cansuspend",
                    "canhibernate",
                    "canreboot",
                    "volume",
                    "name",
                    "version",
                ]
            },
        )

        if system_props:
            info["system"] = {
                "name": system_props.get("name", "Unknown"),
                "version": _format_version(system_props.get("version", {})),
                "volume": system_props.get("volume", 0),
                "can_shutdown": system_props.get("canshutdown", False),
                "can_suspend": system_props.get("cansuspend", False),
                "can_hibernate": system_props.get("canhibernate", False),
                "can_reboot": system_props.get("canreboot", False),
            }

        tv_shows = _query_kodi(config, ip, "VideoLibrary.GetTVShows", {})
        movies = _query_kodi(config, ip, "VideoLibrary.GetMovies", {})
        episodes = _query_kodi(config, ip, "VideoLibrary.GetEpisodes", {})

        info["library"] = {
            "tv_shows": len(tv_shows.get("tvshows", [])) if tv_shows else 0,
            "movies": len(movies.get("movies", [])) if movies else 0,
            "episodes": len(episodes.get("episodes", [])) if episodes else 0,
        }

        active_players = _query_kodi(config, ip, "Player.GetActivePlayers", {})
        if active_players:
            players = cast(list[dict[str, Any]], active_players)
            player_id = players[0].get("playerid")
            player_item = _query_kodi(
                config,
                ip,
                "Player.GetItem",
                {"playerid": player_id, "properties": ["title"]},
            )
            info["player"] = {
                "active": True,
                "type": players[0].get("type", "unknown"),
                "playing": player_item.get("item", {}).get("title", "Unknown")
                if player_item
                else "Unknown",
            }
        else:
            info["player"] = {"active": False}

        addons = _query_kodi(
            config,
            ip,
            "Addons.GetAddons",
            {"enabled": True, "type": "xbmc.addon.video"},
        )
        info["addons"] = {
            "video_addons": len(addons.get("addons", [])) if addons else 0
        }
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)

    return info


def _query_kodi(
    config: Config,
    ip: str,
    method: str,
    params: dict[str, Any],
    timeout: int = 3,
) -> dict[str, Any] | None:
    """Send a JSON-RPC request to Kodi and return the result."""
    try:
        response = requests.post(
            f"http://{ip}:{config.kodi.port}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1,
            },
            timeout=timeout,
        )
        result = response.json()
        return cast(dict[str, Any] | None, result.get("result"))
    except Exception:  # noqa: BLE001
        return None


def _format_version(version_dict: object) -> str:
    """Format a Kodi version dictionary into a readable string."""
    if not isinstance(version_dict, dict) or not version_dict:
        return "Unknown"

    major = version_dict.get("major", "?")
    minor = version_dict.get("minor", 0)
    tag = version_dict.get("tag", "")

    if tag:
        return f"{major}.{minor} {tag}"
    return f"{major}.{minor}"
