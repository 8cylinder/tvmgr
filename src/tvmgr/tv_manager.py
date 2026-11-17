"""Deletion and filesystem helpers for tvmgr."""

from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rich.markup import escape

from .config import Config, PathsConfig, SmbConfig
from .ui import Ui

try:
    import smbc as _smbc
except ImportError:  # pragma: no cover - exercised when pysmbc is unavailable
    _smbc = None

smbc: Any = _smbc

SMB_INSTALL_HINT = """No module named "smbc", see: https://github.com/hamano/pysmbc.

To install with pip or uv, additional libraries need to be installed.
> sudo apt install build-essential pkg-config libsmbclient libsmbclient-dev python3-dev
> pip3 install pysmbc
> uv add pysmbc

Or install the apt package
> apt install python3-smbc
To make apt installed packages available to a venv see,
https://github.com/astral-sh/uv/issues/1483#issuecomment-1955116742
"""

sql = """
    SELECT
        episodeview.strPath || episodeview.strFileName as file
        , episodeview.strTitle
        --, ifnull (episodeview.playCount, 0) as playCount
    FROM
        episode_view as episodeview
    WHERE
        playCount > 0
    ORDER BY
        episodeview.strTitle;
"""


class SmbUnavailableError(RuntimeError):
    """Raised when SMB access is requested without pysmbc installed."""


class ShowFile:
    """Mimic smbc's API for local file actions."""

    def __init__(self, filename: str, paths: PathsConfig) -> None:
        parsed = urlparse(filename).path
        parsed = parsed.replace(paths.smbc_drive, paths.mount_base)
        self.p = Path(parsed)

    def stat(self, _: object) -> os.stat_result:
        """Return the same stat data as smbc's stat function."""
        return self.p.stat()

    def unlink(self, _: object) -> None:
        """Delete the local file."""
        self.p.unlink()


def make_auth_fn(config: SmbConfig) -> Callable[..., tuple[str, str, str]]:
    """Return an authentication callback using the configured credentials."""

    def auth_fn(
        server: str,
        share: str,
        workgroup: str,
        username: str,
        password: str,
    ) -> tuple[str, str, str]:
        del server, share, username, password
        return (config.workgroup or workgroup, config.username, config.password)

    return auth_fn


def delete_files(
    data: Iterable[tuple[str, str]] | sqlite3.Cursor,
    hide_deleted: bool,
    real: bool,
    use_smbc: bool,
    verbose: bool,
    config: Config,
    ui: Ui,
) -> None:
    """Delete watched files, or list them when ``real`` is false."""
    ctx: Any = None
    if use_smbc:
        if smbc is None:
            raise SmbUnavailableError(SMB_INSTALL_HINT)
        ctx = smbc.Context()
        ctx.optionNoAutoAnonymousLogin = True
        ctx.functionAuthData = make_auth_fn(config.smb)

    no_entry_error = getattr(smbc, "NoEntryError", ())
    permission_error = getattr(smbc, "PermissionError", ())

    keep_list = [
        show.replace("_", "").replace(" ", "").lower()
        for show in config.keep_list
    ]

    st_size = 6
    total_size = 0
    for filename, showname in data:
        if not use_smbc:
            ctx = ShowFile(filename, config.paths)
        search_show = showname.replace("_", "").replace(" ", "").lower()
        if search_show in keep_list:
            if verbose:
                ui.out.print(f"skipping: {escape(filename)}")
            continue

        try:
            stats = ctx.stat(filename)
        except ValueError:
            ui.err.print(f"Not an smb file: {escape(filename)}")
            continue
        except no_entry_error:
            if not hide_deleted:
                ui.err.print(f"(A) File does not exist: {escape(filename)}")
            continue
        except TypeError:
            if not hide_deleted:
                ui.err.print(f"(B) File does not exist: {escape(filename)}")
            continue
        except FileNotFoundError:
            if not hide_deleted:
                ui.err.print(f"(C) File does not exist: {escape(filename)}")
            continue
        except permission_error:
            ui.err.print("You do not have permission to access the smb share.")
            break

        size = stats[st_size]
        total_size += size
        prettysize = humanize(size)
        pfilename = Path(filename)
        shortened = os.path.join(*pfilename.parent.parts[-3:])
        full_path = f"{shortened}/{pfilename.name}"

        prefix_len = 9  # "6chars | "
        available = shutil.get_terminal_size((80, 24)).columns - prefix_len
        if len(full_path) > available:
            full_path = full_path[: available - 1] + "…"

        last_slash = full_path.rfind("/")
        if last_slash >= 0:
            dir_part = full_path[: last_slash + 1]
            file_part = full_path[last_slash + 1 :]
        else:
            dir_part = ""
            file_part = full_path

        line = (
            f"[blue]{escape(prettysize.rjust(6))}[/blue]"
            f"[red] | [/red]"
            f"[white dim]{escape(dir_part)}[/white dim]"
            f"[white]{escape(file_part)}[/white]"
        )
        ui.out.print(line, highlight=False, soft_wrap=True)

        if real:
            ctx.unlink(filename)
            if verbose:
                ui.out.print(f"deleted: {escape(filename)}")

    ui.out.print(f"Total size: {humanize(total_size)}")


def humanize(num: int) -> str:
    """Format a byte count using binary units."""
    if num >= 1073741824:
        fnum = num / 1073741824
        sym = "Gb"
    elif num >= 1048576:
        fnum = num / 1048576
        sym = "Mb"
    elif num >= 1024:
        fnum = num / 1024
        sym = "Kb"
    else:
        fnum = num
        sym = "Bytes"

    return f"{int(round(fnum, 0))} {sym}"


def walk_bottom_up(directory: str, video_types: set[str]) -> bool:
    """Return True when a directory tree contains no video files."""
    is_empty = True
    for root, dirs, files in os.walk(directory, topdown=False):
        del dirs
        found_types = set()
        for file in files:
            abs_file = Path(root, file)
            found_types.add(abs_file.suffix)
        if video_types.intersection(found_types):
            is_empty = False
    return is_empty
