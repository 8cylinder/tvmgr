"""Configuration loading for tvmgr."""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import platformdirs

APP_NAME = "tvmgr"

CONFIG_TEMPLATE = """\
# tvmgr configuration file.
#
# Every value below is required. Uncomment each setting, fill it in, then
# re-run the command. Run `tvmgr --config` to print this file's path.

# Titles that must never be deleted, even when Kodi reports them as watched.
# keep_list = ["Deadwood", "Rick and Morty"]

[kodi]
# Port of Kodi's JSON-RPC API (Kodi's own default is 8080).
# port = 8080
# Username and password for Kodi's HTTP API. Use an empty password when Kodi
# does not require one.
# username = "kodi"
# password = ""

[smb]
# Credentials for the SMB share that holds the media.
# username = "sm"
# password = "Password123"
# Workgroup or domain of the SMB server. Use an empty string to fall back to
# the workgroup the server advertises.
# workgroup = ""

[paths]
# The SMB share path as Kodi reports it, and the local directory it is
# mounted at. Used by the --mount access mode.
# smbc_drive = "/Volume_1"
# mount_base = "/home/sm/net1"

[discover]
# Networks scanned by `tvmgr discover`, in CIDR notation.
# networks = ["192.168.0.0/24", "192.168.1.0/24"]
# Seconds to wait for each host to accept a TCP connection.
# timeout = 0.5
"""


class ConfigError(Exception):
    """Raised when the configuration file cannot be read or is invalid."""


@dataclass(frozen=True)
class KodiConfig:
    """Settings used to talk to Kodi."""

    port: int
    username: str
    password: str


@dataclass(frozen=True)
class SmbConfig:
    """Settings used for SMB authentication."""

    username: str
    password: str
    workgroup: str


@dataclass(frozen=True)
class PathsConfig:
    """Path mapping used by the mount access mode."""

    smbc_drive: str
    mount_base: str


@dataclass(frozen=True)
class DiscoverConfig:
    """Settings for the discover command."""

    networks: tuple[str, ...]
    timeout: float


@dataclass(frozen=True)
class Config:
    """The complete tvmgr configuration."""

    keep_list: tuple[str, ...]
    kodi: KodiConfig
    smb: SmbConfig
    paths: PathsConfig
    discover: DiscoverConfig


def config_path() -> Path:
    """Return the platform-specific path to the configuration file."""
    return Path(platformdirs.user_config_dir(APP_NAME)) / "config.toml"


def write_config_template(path: Path) -> None:
    """Write a commented configuration template to ``path``.

    The file may hold credentials, so it is created with owner-only
    permissions.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CONFIG_TEMPLATE, encoding="utf-8")
        path.chmod(0o600)
    except OSError as exc:
        raise ConfigError(
            f"cannot write config template {path}: {exc}"
        ) from exc


def _default_warn(message: str) -> None:
    print(message, file=sys.stderr)


def _unknown_keys(
    table: Mapping[str, Any],
    known: set[str],
    where: str,
    path: Path,
    warn: Callable[[str], None],
) -> None:
    for key in sorted(set(table) - known):
        warn(f"warning: unknown config key {key!r} in {path} ({where})")


def _table(
    data: Mapping[str, Any],
    key: str,
    path: Path,
    warn: Callable[[str], None],
) -> Mapping[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, Mapping):
        raise ConfigError(f"{path}: {key!r} must be a table")
    return value


def _missing(path: Path, key: str) -> ConfigError:
    return ConfigError(f"{path}: missing required key {key!r}")


def _string(value: object, path: Path, key: str) -> str:
    if value is None:
        raise _missing(path, key)
    if not isinstance(value, str):
        raise ConfigError(f"{path}: {key!r} must be a string")
    return value


def _integer(value: object, path: Path, key: str) -> int:
    if value is None:
        raise _missing(path, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path}: {key!r} must be an integer")
    return value


def _number(value: object, path: Path, key: str) -> float:
    if value is None:
        raise _missing(path, key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path}: {key!r} must be a number")
    return float(value)


def _string_list(value: object, path: Path, key: str) -> tuple[str, ...]:
    if value is None:
        raise _missing(path, key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise ConfigError(f"{path}: {key!r} must be a list of strings")
    return tuple(cast(str, item) for item in value)


def _resolve_path(value: str, config_file: Path) -> str:
    resolved = Path(value).expanduser()
    if not resolved.is_absolute():
        resolved = config_file.parent / resolved
    return str(resolved.resolve())


def load_config(
    path: Path | None = None,
    warn: Callable[[str], None] | None = None,
) -> Config:
    """Load the configuration file.

    There are no built-in defaults, so a missing file is an error. A
    commented template is written to the expected location first so the
    required values can be filled in.
    """
    warn = warn or _default_warn
    path = path or config_path()

    if not path.exists():
        try:
            write_config_template(path)
        except ConfigError as exc:
            raise ConfigError(
                f"config file not found: {path}\n"
                f"run `tvmgr --config` to print the expected path"
            ) from exc
        raise ConfigError(
            f"config file not found: {path}\n"
            f"created a template there; fill in the required values "
            f"and run again"
        )

    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc

    _unknown_keys(
        data,
        {"keep_list", "kodi", "smb", "paths", "discover"},
        "top level",
        path,
        warn,
    )

    kodi = _table(data, "kodi", path, warn)
    _unknown_keys(kodi, {"port", "username", "password"}, "kodi", path, warn)
    smb = _table(data, "smb", path, warn)
    _unknown_keys(smb, {"username", "password", "workgroup"}, "smb", path, warn)
    paths = _table(data, "paths", path, warn)
    _unknown_keys(paths, {"smbc_drive", "mount_base"}, "paths", path, warn)
    discover = _table(data, "discover", path, warn)
    _unknown_keys(discover, {"networks", "timeout"}, "discover", path, warn)

    keep_list = _string_list(data.get("keep_list"), path, "keep_list")
    kodi_config = KodiConfig(
        port=_integer(kodi.get("port"), path, "kodi.port"),
        username=_string(kodi.get("username"), path, "kodi.username"),
        password=_string(kodi.get("password"), path, "kodi.password"),
    )
    smb_config = SmbConfig(
        username=_string(smb.get("username"), path, "smb.username"),
        password=_string(smb.get("password"), path, "smb.password"),
        workgroup=_string(smb.get("workgroup"), path, "smb.workgroup"),
    )
    paths_config = PathsConfig(
        smbc_drive=_resolve_path(
            _string(paths.get("smbc_drive"), path, "paths.smbc_drive"), path
        ),
        mount_base=_resolve_path(
            _string(paths.get("mount_base"), path, "paths.mount_base"), path
        ),
    )
    discover_config = DiscoverConfig(
        networks=_string_list(
            discover.get("networks"), path, "discover.networks"
        ),
        timeout=_number(discover.get("timeout"), path, "discover.timeout"),
    )

    return Config(
        keep_list=keep_list,
        kodi=kodi_config,
        smb=smb_config,
        paths=paths_config,
        discover=discover_config,
    )
