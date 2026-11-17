import tomllib
from pathlib import Path

import pytest
from conftest import (
    CONFIG_TOML,
    config_data,
    config_toml,
    drop_config_key,
    dump_toml,
    write_config,
)

from tvmgr.config import (
    CONFIG_TEMPLATE,
    ConfigError,
    config_path,
    load_config,
    write_config_template,
)


def test_config_path_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_path() == tmp_path / "tvmgr" / "config.toml"


def test_missing_config_writes_template_and_errors(tmp_path):
    path = tmp_path / "tvmgr" / "config.toml"
    with pytest.raises(ConfigError, match="created a template"):
        load_config(path)

    assert path.is_file()
    content = path.read_text()
    assert "[kodi]" in content
    assert "# port = 8080" in content
    assert path.stat().st_mode & 0o777 == 0o600


def test_template_has_only_commented_settings():
    assert tomllib.loads(CONFIG_TEMPLATE) == {
        "kodi": {},
        "smb": {},
        "paths": {},
        "discover": {},
    }


def test_template_write_failure_is_reported(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    with pytest.raises(ConfigError, match="cannot write config template"):
        write_config_template(blocker / "config.toml")


def test_unwritable_config_dir_only_hints_at_path(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    with pytest.raises(ConfigError, match="run `tvmgr --config`"):
        load_config(blocker / "config.toml")


def test_full_config_is_parsed(tmp_path):
    config = load_config(write_config(tmp_path, CONFIG_TOML))
    assert config.keep_list == ("Deadwood", "Rick and Morty")
    assert config.kodi.port == 8080
    assert config.smb.username == "sm"
    assert config.paths.smbc_drive == "/Volume_1"
    assert config.discover.timeout == 0.5


def test_valid_config_overrides_values(tmp_path):
    config_file = write_config(
        tmp_path,
        config_toml(
            {
                "keep_list": ["Alpha", "Beta"],
                "kodi.port": 9000,
                "kodi.username": "me",
                "kodi.password": "secret",
                "smb.username": "user",
                "smb.password": "pass",
                "smb.workgroup": "WORK",
                "paths.smbc_drive": "/Volume_2",
                "paths.mount_base": "mnt/media",
                "discover.networks": ["10.0.0.0/24"],
                "discover.timeout": 1.5,
            }
        ),
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
    config_file = write_config(tmp_path, "not = [valid")
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(config_file)


def test_unreadable_config_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="cannot read config file"):
        load_config(tmp_path)


def test_unknown_keys_warn(tmp_path):
    data = config_data()
    data["unknown_top"] = True
    data["kodi"]["unknown_kodi"] = "x"
    data["smb"]["unknown_smb"] = 1
    data["paths"]["unknown_paths"] = 2
    data["discover"]["unknown_discover"] = 3
    config_file = write_config(tmp_path, dump_toml(data))
    messages: list[str] = []
    load_config(config_file, warn=messages.append)
    joined = "\n".join(messages)
    assert "unknown_top" in joined
    assert "unknown_kodi" in joined
    assert "unknown_smb" in joined
    assert "unknown_paths" in joined
    assert "unknown_discover" in joined


@pytest.mark.parametrize(
    ("dotted", "value", "message"),
    [
        ("keep_list", "nope", "keep_list"),
        ("keep_list", [1], "keep_list"),
        ("kodi", 1, "'kodi' must be a table"),
        ("kodi.port", "nope", "kodi.port"),
        ("kodi.port", True, "kodi.port"),
        ("kodi.username", 1, "kodi.username"),
        ("smb.workgroup", 1, "smb.workgroup"),
        ("paths.smbc_drive", 1, "paths.smbc_drive"),
        ("discover.timeout", "x", "discover.timeout"),
        ("discover.timeout", True, "discover.timeout"),
        ("discover.networks", "x", "discover.networks"),
        ("discover.networks", [1], "discover.networks"),
    ],
)
def test_invalid_types(tmp_path, dotted, value, message):
    config_file = write_config(tmp_path, config_toml({dotted: value}))
    with pytest.raises(ConfigError, match=message):
        load_config(config_file)


@pytest.mark.parametrize(
    "dotted",
    [
        "keep_list",
        "kodi.port",
        "kodi.username",
        "kodi.password",
        "smb.username",
        "smb.password",
        "smb.workgroup",
        "paths.smbc_drive",
        "paths.mount_base",
        "discover.networks",
        "discover.timeout",
    ],
)
def test_missing_required_key(tmp_path, dotted):
    config_file = write_config(tmp_path, dump_toml(drop_config_key(dotted)))
    with pytest.raises(ConfigError, match=f"missing required key '{dotted}'"):
        load_config(config_file)


def test_missing_section_is_an_error(tmp_path):
    data = config_data()
    del data["kodi"]
    config_file = write_config(tmp_path, dump_toml(data))
    with pytest.raises(ConfigError, match="missing required key 'kodi.port'"):
        load_config(config_file)


def test_empty_config_file_is_an_error(tmp_path):
    config_file = write_config(tmp_path, "")
    with pytest.raises(ConfigError, match="missing required key 'keep_list'"):
        load_config(config_file)


def test_default_warning_goes_to_stderr(tmp_path, capsys):
    data = config_data()
    data["unknown"] = True
    config_file = write_config(tmp_path, dump_toml(data))
    load_config(config_file)
    assert "unknown config key" in capsys.readouterr().err


def test_expanduser_in_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    config_file = write_config(
        tmp_path, config_toml({"paths.mount_base": "~/media"})
    )
    config = load_config(config_file)
    assert config.paths.mount_base == str((Path(tmp_path) / "media").resolve())
