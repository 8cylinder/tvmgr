from pathlib import Path

import pytest

from tvmgr.config import (
    Config,
    ConfigError,
    config_path,
    load_config,
)


def test_config_path_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "tvmgr" / "config.toml"


def test_missing_config_returns_defaults(tmp_path):
    config = load_config(tmp_path / "missing.toml")
    assert isinstance(config, Config)
    assert "Deadwood" in config.keep_list
    assert config.kodi.port == 8080
    assert config.discover.timeout == 0.5


def test_valid_config_overrides_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
keep_list = ["Alpha", "Beta"]

[kodi]
port = 9000
username = "me"
password = "secret"

[smb]
username = "user"
password = "pass"
workgroup = "WORK"

[paths]
smbc_drive = "/Volume_2"
mount_base = "mnt/media"

[discover]
networks = ["10.0.0.0/24"]
timeout = 1.5
"""
    )
    config = load_config(config_file)
    assert config.keep_list == ("Alpha", "Beta")
    assert config.kodi.port == 9000
    assert config.kodi.username == "me"
    assert config.smb.workgroup == "WORK"
    assert config.paths.smbc_drive == "/Volume_2"
    assert config.paths.mount_base == str((tmp_path / "mnt/media").resolve())
    assert config.discover.networks == ("10.0.0.0/24",)
    assert config.discover.timeout == 1.5


def test_invalid_toml_names_path(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("not = [valid")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(config_file)


def test_unreadable_config_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="cannot read config file"):
        load_config(tmp_path)


def test_unknown_keys_warn(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
unknown_top = true

[kodi]
port = 8080
unknown_kodi = "x"

[smb]
unknown_smb = 1

[paths]
unknown_paths = 2

[discover]
unknown_discover = 3
"""
    )
    messages: list[str] = []
    load_config(config_file, warn=messages.append)
    joined = "\n".join(messages)
    assert "unknown_top" in joined
    assert "unknown_kodi" in joined
    assert "unknown_smb" in joined
    assert "unknown_paths" in joined
    assert "unknown_discover" in joined


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("keep_list = 'nope'", "keep_list"),
        ("keep_list = [1]", "keep_list"),
        ("kodi = 1", "'kodi' must be a table"),
        ("[kodi]\nport = 'nope'", "kodi.port"),
        ("[kodi]\nport = true", "kodi.port"),
        ("[kodi]\nusername = 1", "kodi.username"),
        ("[smb]\nworkgroup = 1", "smb.workgroup"),
        ("[paths]\nsmbc_drive = 1", "paths.smbc_drive"),
        ("[discover]\ntimeout = 'x'", "discover.timeout"),
        ("[discover]\ntimeout = true", "discover.timeout"),
        ("[discover]\nnetworks = 'x'", "discover.networks"),
        ("[discover]\nnetworks = [1]", "discover.networks"),
    ],
)
def test_invalid_types(tmp_path, content, message):
    config_file = tmp_path / "config.toml"
    config_file.write_text(content)
    with pytest.raises(ConfigError, match=message):
        load_config(config_file)


def test_default_warning_goes_to_stderr(tmp_path, capsys):
    config_file = tmp_path / "config.toml"
    config_file.write_text("unknown = true\n")
    load_config(config_file)
    assert "unknown config key" in capsys.readouterr().err


def test_empty_config_file_uses_defaults(tmp_path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    assert load_config(config_file) == Config()


def test_expanduser_in_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        """
[paths]
mount_base = "~/media"
"""
    )
    config = load_config(config_file)
    assert config.paths.mount_base == str((Path(tmp_path) / "media").resolve())
