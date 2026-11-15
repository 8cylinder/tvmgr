"""Configuration loading for tvmgr."""

from __future__ import annotations

import sys
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import platformdirs

APP_NAME = "tvmgr"

DEFAULT_KEEP_LIST = ("Deadwood", "Rick and Morty")
DEFAULT_KODI_PORT = 8080
DEFAULT_KODI_USERNAME = "kodi"
DEFAULT_KODI_PASSWORD = ""
DEFAULT_SMB_USERNAME = "sm"
DEFAULT_SMB_PASSWORD = "Password123"
DEFAULT_SMB_WORKGROUP = ""
DEFAULT_SMBC_DRIVE = "/Volume_1"
DEFAULT_MOUNT_BASE = "/home/sm/net1"
DEFAULT_NETWORKS = ("192.168.0.0/24", "192.168.1.0/24")
DEFAULT_DISCOVER_TIMEOUT = 0.5


class ConfigError(Exception):
    """Raised when the configuration file cannot be read or is invalid."""


@dataclass(frozen=True)
class KodiConfig:
    """Settings used to talk to Kodi."""

    port: int = DEFAULT_KODI_PORT
    username: str = DEFAULT_KODI_USERNAME
    password: str = DEFAULT_KODI_PASSWORD


@dataclass(frozen=True)
class SmbConfig:
    """Settings used for SMB authentication."""

    username: str = DEFAULT_SMB_USERNAME
    password: str = DEFAULT_SMB_PASSWORD
    workgroup: str = DEFAULT_SMB_WORKGROUP


@dataclass(frozen=True)
class PathsConfig:
    """Path mapping used by the mount access mode."""

    smbc_drive: str = DEFAULT_SMBC_DRIVE
    mount_base: str = DEFAULT_MOUNT_BASE


@dataclass(frozen=True)
class DiscoverConfig:
    """Defaults for the discover command."""

    networks: tuple[str, ...] = DEFAULT_NETWORKS
    timeout: float = DEFAULT_DISCOVER_TIMEOUT


@dataclass(frozen=True)
class Config:
    """The complete tvmgr configuration."""

    keep_list: tuple[str, ...] = DEFAULT_KEEP_LIST
    kodi: KodiConfig = field(default_factory=KodiConfig)
    smb: SmbConfig = field(default_factory=SmbConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    discover: DiscoverConfig = field(default_factory=DiscoverConfig)


def config_path() -> Path:
    """Return the platform-specific path to the configuration file."""
    return Path(platformdirs.user_config_dir(APP_NAME)) / "config.toml"


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


def _string(value: object, path: Path, key: str, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise ConfigError(f"{path}: {key!r} must be a string")
    return value


def _integer(value: object, path: Path, key: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{path}: {key!r} must be an integer")
    return value


def _number(value: object, path: Path, key: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{path}: {key!r} must be a number")
    return float(value)


def _string_list(
    value: object,
    path: Path,
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    if value is None:
        return default
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
    """Load the configuration file, returning defaults when it is missing."""
    warn = warn or _default_warn
    path = path or config_path()

    if not path.exists():
        return Config()

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

    smbc_drive = _resolve_path(
        _string(
            paths.get("smbc_drive"),
            path,
            "paths.smbc_drive",
            DEFAULT_SMBC_DRIVE,
        ),
        path,
    )
    mount_base = _resolve_path(
        _string(
            paths.get("mount_base"),
            path,
            "paths.mount_base",
            DEFAULT_MOUNT_BASE,
        ),
        path,
    )

    return Config(
        keep_list=_string_list(
            data.get("keep_list"), path, "keep_list", DEFAULT_KEEP_LIST
        ),
        kodi=KodiConfig(
            port=_integer(
                kodi.get("port"), path, "kodi.port", DEFAULT_KODI_PORT
            ),
            username=_string(
                kodi.get("username"),
                path,
                "kodi.username",
                DEFAULT_KODI_USERNAME,
            ),
            password=_string(
                kodi.get("password"),
                path,
                "kodi.password",
                DEFAULT_KODI_PASSWORD,
            ),
        ),
        smb=SmbConfig(
            username=_string(
                smb.get("username"), path, "smb.username", DEFAULT_SMB_USERNAME
            ),
            password=_string(
                smb.get("password"), path, "smb.password", DEFAULT_SMB_PASSWORD
            ),
            workgroup=_string(
                smb.get("workgroup"),
                path,
                "smb.workgroup",
                DEFAULT_SMB_WORKGROUP,
            ),
        ),
        paths=PathsConfig(smbc_drive=smbc_drive, mount_base=mount_base),
        discover=DiscoverConfig(
            networks=_string_list(
                discover.get("networks"),
                path,
                "discover.networks",
                DEFAULT_NETWORKS,
            ),
            timeout=_number(
                discover.get("timeout"),
                path,
                "discover.timeout",
                DEFAULT_DISCOVER_TIMEOUT,
            ),
        ),
    )
