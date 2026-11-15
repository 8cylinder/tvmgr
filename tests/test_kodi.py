from unittest.mock import Mock

import pytest
import requests

from tvmgr.config import Config
from tvmgr.kodi import (
    KodiError,
    _format_version,
    _query_kodi,
    get_kodi_info,
    get_watched_media,
)


def _response(payload):
    response = Mock()
    response.json.return_value = payload
    return response


def test_get_watched_media_tv(monkeypatch):
    response = _response(
        {
            "result": {
                "episodes": [
                    {"file": "smb://server/one.mkv", "showtitle": "Show"},
                ]
            }
        }
    )
    get = Mock(return_value=response)
    monkeypatch.setattr("tvmgr.kodi.requests.get", get)

    result = get_watched_media("1.2.3.4", True, Config())

    assert result == [("smb://server/one.mkv", "Show")]
    endpoint, payload = get.call_args.args
    assert endpoint == "http://1.2.3.4:8080/jsonrpc"
    assert "VideoLibrary.GetEpisodes" in payload["request"]


def test_get_watched_media_movies(monkeypatch):
    response = _response(
        {
            "result": {
                "movies": [
                    {
                        "file": "smb://server/movie.mkv",
                        "originaltitle": "Movie",
                    },
                ]
            }
        }
    )
    get = Mock(return_value=response)
    monkeypatch.setattr("tvmgr.kodi.requests.get", get)

    assert get_watched_media("1.2.3.4", False, Config()) == [
        ("smb://server/movie.mkv", "Movie")
    ]
    assert "VideoLibrary.GetMovies" in get.call_args.args[1]["request"]


def test_get_watched_media_connection_error(monkeypatch):
    monkeypatch.setattr(
        "tvmgr.kodi.requests.get",
        Mock(side_effect=requests.exceptions.ConnectionError()),
    )
    with pytest.raises(KodiError, match="network is unreachable"):
        get_watched_media("1.2.3.4", True, Config())


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"result": {}},
        {"result": {"episodes": [{}]}},
    ],
)
def test_get_watched_media_bad_response(monkeypatch, payload):
    monkeypatch.setattr(
        "tvmgr.kodi.requests.get",
        Mock(return_value=_response(payload)),
    )
    with pytest.raises(KodiError, match="unexpected response"):
        get_watched_media("1.2.3.4", True, Config())


def test_get_watched_media_invalid_json(monkeypatch):
    response = Mock()
    response.json.side_effect = ValueError("bad json")
    monkeypatch.setattr("tvmgr.kodi.requests.get", Mock(return_value=response))
    with pytest.raises(KodiError, match="unexpected response"):
        get_watched_media("1.2.3.4", True, Config())


def test_query_kodi_success(monkeypatch):
    response = _response({"result": {"name": "Kodi"}})
    post = Mock(return_value=response)
    monkeypatch.setattr("tvmgr.kodi.requests.post", post)

    assert _query_kodi(Config(), "1.2.3.4", "Method", {"a": 1}) == {
        "name": "Kodi"
    }
    post.assert_called_once()
    assert post.call_args.kwargs["json"]["method"] == "Method"
    assert post.call_args.kwargs["timeout"] == 3


def test_query_kodi_failure(monkeypatch):
    monkeypatch.setattr(
        "tvmgr.kodi.requests.post",
        Mock(side_effect=requests.exceptions.Timeout()),
    )
    assert _query_kodi(Config(), "1.2.3.4", "Method", {}) is None


def test_get_kodi_info_full(monkeypatch):
    responses = {
        "System.GetProperties": {
            "name": "Living Room",
            "version": {"major": 20, "minor": 2, "tag": "Nexus"},
            "volume": 50,
            "canshutdown": True,
        },
        "VideoLibrary.GetTVShows": {"tvshows": [1, 2]},
        "VideoLibrary.GetMovies": {"movies": [1]},
        "VideoLibrary.GetEpisodes": {"episodes": [1, 2, 3]},
        "Player.GetActivePlayers": [{"playerid": 1, "type": "video"}],
        "Player.GetItem": {"item": {"title": "Episode"}},
        "Addons.GetAddons": {"addons": [1, 2, 3, 4]},
    }

    def fake_query(_config, _ip, method, _params, timeout=3):
        return responses[method]

    monkeypatch.setattr("tvmgr.kodi._query_kodi", fake_query)
    info = get_kodi_info("1.2.3.4", Config())

    assert info["url"] == "http://1.2.3.4:8080"
    assert info["system"]["name"] == "Living Room"
    assert info["system"]["version"] == "20.2 Nexus"
    assert info["library"] == {"tv_shows": 2, "movies": 1, "episodes": 3}
    assert info["player"] == {
        "active": True,
        "type": "video",
        "playing": "Episode",
    }
    assert info["addons"] == {"video_addons": 4}
    assert "error" not in info


def test_get_kodi_info_idle_and_no_data(monkeypatch):
    def fake_query(_config, _ip, method, _params, timeout=3):
        if method == "System.GetProperties":
            return None
        if method == "Player.GetActivePlayers":
            return []
        return None

    monkeypatch.setattr("tvmgr.kodi._query_kodi", fake_query)
    info = get_kodi_info("1.2.3.4", Config())

    assert info["system"] == {}
    assert info["library"] == {"tv_shows": 0, "movies": 0, "episodes": 0}
    assert info["player"] == {"active": False}
    assert info["addons"] == {"video_addons": 0}


def test_get_kodi_info_error(monkeypatch):
    monkeypatch.setattr(
        "tvmgr.kodi._query_kodi",
        Mock(side_effect=RuntimeError("boom")),
    )
    info = get_kodi_info("1.2.3.4", Config())
    assert info["error"] == "boom"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "Unknown"),
        ({}, "Unknown"),
        ("nope", "Unknown"),
        ({"major": 20, "minor": 2}, "20.2"),
        ({"major": 20, "minor": 2, "tag": "Nexus"}, "20.2 Nexus"),
        ({"major": 21}, "21.0"),
    ],
)
def test_format_version(value, expected):
    assert _format_version(value) == expected
