import sqlite3
import tomllib
from pathlib import Path

import pytest
from click.testing import CliRunner

from tvmgr import cli
from tvmgr.cli import main
from tvmgr.kodi import KodiError
from tvmgr.tv_manager import SmbUnavailableError


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "HOME": str(tmp_path / "home"),
    }


def _invoke(args, tmp_path, **kwargs):
    return CliRunner().invoke(main, args, env=_env(tmp_path), **kwargs)


def _write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config" / "tvmgr" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["-h"],
        ["viajson", "--help"],
        ["viadb", "-h"],
        ["cleanup", "--help"],
        ["discover", "-h"],
    ],
)
def test_help_variants(args, tmp_path):
    result = _invoke(args, tmp_path)
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "\x1b[" not in result.output


def test_no_arguments_shows_help(tmp_path):
    result = _invoke([], tmp_path)
    assert "Usage:" in result.output
    assert "\x1b[" not in result.output


def test_version_matches_pyproject(tmp_path):
    version = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text()
    )["project"]["version"]
    result = _invoke(["--version"], tmp_path)
    assert result.exit_code == 0
    assert result.output.strip() == f"tvmgr, version {version}"
    assert "\x1b[" not in result.output


def test_version_stays_plain_when_color_is_forced(tmp_path):
    result = _invoke(["--color", "always", "--version"], tmp_path)
    assert result.exit_code == 0
    assert "\x1b[" not in result.output


def test_config_prints_path_only(tmp_path):
    result = _invoke(["--config"], tmp_path)
    assert result.exit_code == 0
    expected = tmp_path / "config" / "tvmgr" / "config.toml"
    assert result.stdout.strip() == str(expected)
    assert not expected.exists()
    assert "\x1b[" not in result.stdout


def test_invalid_config_exits_nonzero(tmp_path):
    _write_config(tmp_path, "not = [valid")
    result = _invoke(["cleanup"], tmp_path)
    assert result.exit_code != 0
    assert "invalid TOML" in result.output + result.stderr


def test_unknown_config_key_warns(tmp_path):
    _write_config(tmp_path, "unknown = true\n")
    result = _invoke(["cleanup"], tmp_path)
    assert result.exit_code == 0
    assert "unknown config key" in result.stderr


def test_cleanup_show_modes(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    full = tmp_path / "full"
    full.mkdir()
    (full / "episode.mkv").write_text("x")

    result = _invoke(["cleanup", str(empty), str(full)], tmp_path)
    assert result.exit_code == 0
    assert str(empty) in result.output
    assert str(full) not in result.output

    result = _invoke(
        ["cleanup", "--show", "f", str(empty), str(full)], tmp_path
    )
    assert str(full) in result.output
    assert str(empty) not in result.output

    result = _invoke(
        ["cleanup", "--show", "b", str(empty), str(full)], tmp_path
    )
    assert str(empty) in result.output
    assert str(full) in result.output


def test_cleanup_null_delimiter(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _invoke(["cleanup", "--null", str(empty)], tmp_path)
    assert result.exit_code == 0
    assert f"{empty}\0" in result.stdout


def test_cleanup_color_modes(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()

    always = _invoke(["--color", "always", "cleanup", str(empty)], tmp_path)
    assert "\x1b[" in always.output

    never = _invoke(["--color", "never", "cleanup", str(empty)], tmp_path)
    assert "\x1b[" not in never.output

    auto = _invoke(["cleanup", str(empty)], tmp_path)
    assert "\x1b[" not in auto.output


def test_viajson_passes_tv_to_delete(monkeypatch, tmp_path):
    calls = {}

    monkeypatch.setattr(
        cli,
        "get_watched_media",
        lambda ip, is_tv, config: [("smb://server/a.mkv", "A")],
    )

    def fake_delete(data, hide, real, use_smbc, verbose, config, ui):
        calls.update(
            data=list(data),
            hide=hide,
            real=real,
            use_smbc=use_smbc,
            verbose=verbose,
        )

    monkeypatch.setattr(cli, "delete_files", fake_delete)
    result = _invoke(["viajson", "1.2.3.4", "--real", "-v"], tmp_path)
    assert result.exit_code == 0
    assert calls == {
        "data": [("smb://server/a.mkv", "A")],
        "hide": False,
        "real": True,
        "use_smbc": True,
        "verbose": True,
    }


def test_viajson_movies(monkeypatch, tmp_path):
    seen = {}

    def fake_watched(ip, is_tv, config):
        seen["is_tv"] = is_tv
        return []

    monkeypatch.setattr(cli, "get_watched_media", fake_watched)
    monkeypatch.setattr(cli, "delete_files", lambda *args, **kwargs: None)
    result = _invoke(["viajson", "1.2.3.4", "--movies"], tmp_path)
    assert result.exit_code == 0
    assert seen["is_tv"] is False


def test_viajson_kodi_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cli,
        "get_watched_media",
        lambda *args: (_ for _ in ()).throw(KodiError("unreachable")),
    )
    result = _invoke(["viajson", "1.2.3.4"], tmp_path)
    assert result.exit_code != 0
    assert "unreachable" in result.output + result.stderr


def test_viajson_smb_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "get_watched_media", lambda *args: [])
    monkeypatch.setattr(
        cli,
        "delete_files",
        lambda *args: (_ for _ in ()).throw(SmbUnavailableError("no smbc")),
    )
    result = _invoke(["viajson", "1.2.3.4"], tmp_path)
    assert result.exit_code != 0
    assert "no smbc" in result.output + result.stderr


def _make_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "create table episode_view "
        "(strPath text, strFileName text, strTitle text, playCount integer)"
    )
    connection.execute(
        "insert into episode_view values (?, ?, ?, ?)",
        ("smb://server/Volume_1/Show/", "episode.mkv", "Episode", 1),
    )
    connection.commit()
    connection.close()


def test_viadb_reads_database(monkeypatch, tmp_path):
    database = tmp_path / "videos.db"
    _make_database(database)
    seen = {}

    def fake_delete(data, hide, real, use_smbc, verbose, config, ui):
        seen["data"] = list(data)
        seen["use_smbc"] = use_smbc

    monkeypatch.setattr(cli, "delete_files", fake_delete)
    result = _invoke(["viadb", str(database)], tmp_path)
    assert result.exit_code == 0
    assert seen["data"] == [
        ("smb://server/Volume_1/Show/episode.mkv", "Episode")
    ]
    assert seen["use_smbc"] is True


def test_viadb_mount_mode(monkeypatch, tmp_path):
    database = tmp_path / "videos.db"
    _make_database(database)
    seen = {}

    def fake_delete(data, hide, real, use_smbc, verbose, config, ui):
        seen["use_smbc"] = use_smbc

    monkeypatch.setattr(cli, "delete_files", fake_delete)
    result = _invoke(["viadb", str(database), "--mount"], tmp_path)
    assert result.exit_code == 0
    assert seen["use_smbc"] is False


def test_viadb_smb_unavailable(monkeypatch, tmp_path):
    database = tmp_path / "videos.db"
    _make_database(database)
    monkeypatch.setattr(
        cli,
        "delete_files",
        lambda *args: (_ for _ in ()).throw(SmbUnavailableError("no smbc")),
    )
    result = _invoke(["viadb", str(database)], tmp_path)
    assert result.exit_code != 0
    assert "no smbc" in result.output + result.stderr


def test_viadb_missing_database(tmp_path):
    result = _invoke(["viadb", str(tmp_path / "missing.db")], tmp_path)
    assert result.exit_code != 0


def test_discover_no_devices(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_kodi", lambda *args: [])
    result = _invoke(["discover"], tmp_path)
    assert result.exit_code == 0
    assert "No Kodi devices found" in result.output


def test_discover_prints_details(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_kodi", lambda *args: ["1.2.3.4"])
    monkeypatch.setattr(
        cli,
        "get_kodi_info",
        lambda *args: {
            "system": {
                "name": "Living Room",
                "version": "20.2 Nexus",
                "volume": 50,
            },
            "url": "http://1.2.3.4:8080",
            "library": {"tv_shows": 1, "episodes": 2, "movies": 3},
            "player": {"active": True, "playing": "Episode", "type": "video"},
            "addons": {"video_addons": 4},
            "error": "minor problem",
        },
    )
    result = _invoke(["discover"], tmp_path)
    assert result.exit_code == 0
    assert "Living Room" in result.output
    assert "20.2 Nexus" in result.output
    assert "TV Shows: 1" in result.output
    assert "Playing: Episode" in result.output
    assert "Video Add-ons: 4" in result.output
    assert "minor problem" in result.output


def test_discover_idle_player(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "discover_kodi", lambda *args: ["1.2.3.4"])
    monkeypatch.setattr(
        cli,
        "get_kodi_info",
        lambda *args: {"player": {"active": False}},
    )
    result = _invoke(["discover"], tmp_path)
    assert result.exit_code == 0
    assert "Status:  Idle" in result.output


def test_discover_uses_config_defaults(monkeypatch, tmp_path):
    _write_config(
        tmp_path,
        """
[discover]
networks = ["10.0.0.0/24"]
timeout = 1.5
""",
    )
    seen = {}

    def fake_discover(networks, timeout):
        seen["networks"] = networks
        seen["timeout"] = timeout
        return []

    monkeypatch.setattr(cli, "discover_kodi", fake_discover)
    result = _invoke(["discover"], tmp_path)
    assert result.exit_code == 0
    assert seen == {"networks": ["10.0.0.0/24"], "timeout": 1.5}


def test_discover_cli_overrides_config(monkeypatch, tmp_path):
    _write_config(
        tmp_path,
        """
[discover]
networks = ["10.0.0.0/24"]
timeout = 1.5
""",
    )
    seen = {}

    def fake_discover(networks, timeout):
        seen["networks"] = networks
        seen["timeout"] = timeout
        return []

    monkeypatch.setattr(cli, "discover_kodi", fake_discover)
    result = _invoke(
        [
            "discover",
            "--network",
            "192.168.9.0/24",
            "--timeout",
            "2",
        ],
        tmp_path,
    )
    assert result.exit_code == 0
    assert seen == {"networks": ["192.168.9.0/24"], "timeout": 2.0}


def test_completions_writes_file(tmp_path):
    result = _invoke(["--completions"], tmp_path)
    assert result.exit_code == 0
    destination = (
        tmp_path / "data" / "bash-completion" / "completions" / "tvmgr.bash"
    )
    assert result.stdout.strip() == str(destination)
    assert destination.exists()
    assert "\x1b[" not in result.stdout


def test_module_entrypoint(monkeypatch, capsys):
    import runpy
    import sys

    monkeypatch.setattr(sys, "argv", ["tvmgr", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("tvmgr", run_name="__main__")
    assert exc_info.value.code == 0
    assert "tvmgr, version" in capsys.readouterr().out
