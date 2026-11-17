"""Shared pytest helpers."""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

from tvmgr.config import (
    Config,
    DiscoverConfig,
    KodiConfig,
    PathsConfig,
    SmbConfig,
)

CONFIG_DATA: dict[str, Any] = {
    "keep_list": ["Deadwood", "Rick and Morty"],
    "kodi": {"port": 8080, "username": "kodi", "password": ""},
    "smb": {"username": "sm", "password": "Password123", "workgroup": ""},
    "paths": {"smbc_drive": "/Volume_1", "mount_base": "/home/sm/net1"},
    "discover": {
        "networks": ["192.168.0.0/24", "192.168.1.0/24"],
        "timeout": 0.5,
    },
}


def _format(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format(item) for item in value) + "]"
    raise TypeError(f"cannot render {value!r} as TOML")


def dump_toml(data: dict[str, Any]) -> str:
    """Render a simple config mapping as TOML."""
    lines = [
        f"{key} = {_format(value)}"
        for key, value in data.items()
        if not isinstance(value, dict)
    ]
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"\n[{key}]")
            lines.extend(
                f"{inner} = {_format(item)}" for inner, item in value.items()
            )
    return "\n".join(lines) + "\n"


def _walk(
    data: MutableMapping[str, Any], dotted: str
) -> tuple[MutableMapping[str, Any], str]:
    *parents, key = dotted.split(".")
    table: MutableMapping[str, Any] = data
    for parent in parents:
        table = table[parent]
    return table, key


def config_data(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a copy of the base config data with dotted-key overrides."""
    data = deepcopy(CONFIG_DATA)
    for dotted, value in (overrides or {}).items():
        table, key = _walk(data, dotted)
        table[key] = value
    return data


def drop_config_key(dotted: str) -> dict[str, Any]:
    """Return base config data without the given dotted key."""
    data = deepcopy(CONFIG_DATA)
    table, key = _walk(data, dotted)
    del table[key]
    return data


def config_toml(overrides: dict[str, Any] | None = None) -> str:
    """Render the base config data, with dotted-key overrides, as TOML."""
    return dump_toml(config_data(overrides))


CONFIG_TOML = config_toml()


def write_config(tmp_path: Path, content: str = CONFIG_TOML) -> Path:
    """Write ``content`` to a config file under ``tmp_path``."""
    path = tmp_path / "config.toml"
    path.write_text(content)
    return path


def make_config(**overrides: Any) -> Config:
    """Return a fully populated Config, with optional field overrides."""
    base = Config(
        keep_list=("Deadwood", "Rick and Morty"),
        kodi=KodiConfig(port=8080, username="kodi", password=""),
        smb=SmbConfig(username="sm", password="Password123", workgroup=""),
        paths=PathsConfig(smbc_drive="/Volume_1", mount_base="/home/sm/net1"),
        discover=DiscoverConfig(
            networks=("192.168.0.0/24", "192.168.1.0/24"), timeout=0.5
        ),
    )
    return replace(base, **overrides) if overrides else base
