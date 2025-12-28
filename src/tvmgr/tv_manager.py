#!/usr/bin/env python3

"""#!/usr/bin/env bin-python.bash"""

import os
import sys
import sqlite3
import json
from typing import Any
import requests

try:
    import smbc  # type: ignore
except ModuleNotFoundError:
    print("""
        No module named "smbc", see: https://github.com/hamano/pysmbc.

        To install vip pip or uv, additional libraries need to be installed.
        > sudo apt install build-essential pkg-config libsmbclient libsmbclient-dev python3-dev
        > pip3 install pysmbc
        > uv add pysmbc

        Or install the apt package
        > apt install python3-smbc
        To make apt installed packages available to a venv see,
        https://github.com/astral-sh/uv/issues/1483#issuecomment-1955116742
    """)
    exit()

import click
import logging as l
from pathlib import Path
from urllib.parse import urlparse

# set up logging -- eg: l.error('This is an error')
this_file = __file__
log_file = "{}.log".format(this_file)
l.basicConfig(format="%(asctime)s -- %(levelname)s -- %(message)s", filename=log_file)

keep_list = ["Deadwood", "Rick and Morty"]
# convert show list to to names without spaces or underscores so it
# can be matched if the comparison name has either
keep_list = [show.replace("_", "").replace(" ", "").lower() for show in keep_list]

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


class ShowFile:
    """Mimic smbc's api

    This provides an api that matches smbc's api but for local file
    actions
    """

    smbc_drive = "/Volume_1"
    mount_base = "/home/sm/net1"

    def __init__(self, filename: str) -> None:
        parsed = urlparse(filename).path
        parsed = parsed.replace(self.smbc_drive, self.mount_base)
        self.p = Path(parsed)
        if not self.p.exists:
            print("{} does not exist".format(self.p))

    def stat(self, _: Any) -> Any:
        """Return the same stat data as smbc stat

        smbc's stat function requires a filename, but this one
        doesn't.  To maintain compatability, a value can be passed in,
        but it is ignored.
        """
        return self.p.stat()

    def unlink(self, _: Any) -> None:
        self.p.unlink()


def auth_fn(
    server: str, share: str, workgroup: str, username: str, password: str
) -> tuple[str, str, str]:
    # settings = (workgroup, username, password)
    settings = (workgroup, "sm", "Password123")
    return settings


def delete_files(
    data: list[tuple[str, str]] | sqlite3.Cursor,
    hide_deleted: bool,
    real: bool,
    use_smbc: bool,
    verbose: bool,
) -> None:
    ctx: Any
    if use_smbc:
        ctx = smbc.Context()
        ctx.optionNoAutoAnonymousLogin = True
        ctx.functionAuthData = auth_fn

    ST_SIZE = 6
    total_size = 0
    for filename, showname in data:
        if not use_smbc:
            ctx = ShowFile(filename)
        search_show = showname.replace("_", "").replace(" ", "").lower()
        if search_show in keep_list:
            if verbose:
                click.echo(f"skipping: {filename}")
            continue

        try:
            stats = ctx.stat(filename)
        except ValueError:
            click.echo("Not an smb file: %s" % filename, err=True)
            continue  # not an smb:// uri
        except smbc.NoEntryError:
            if not hide_deleted:
                click.echo("(A) File does not exist: %s" % filename, err=True)
            continue  # does not exist
        except TypeError:
            if not hide_deleted:
                click.echo("(B) File does not exist: %s" % filename, err=True)
            continue  # does not exist
        except FileNotFoundError:
            if not hide_deleted:
                click.echo("(C) File does not exist: %s" % filename, err=True)
            continue  # does not exist
        except smbc.PermissionError:
            click.echo("You do not have permission to access the smb share.")
            break

        size = stats[ST_SIZE]

        # continue
        total_size += size
        prettysize = humanize(size)
        pfilename = Path(filename)
        shortened = os.path.join(*pfilename.parent.parts[-3:])

        fancy_filename = click.style(
            f"{shortened}/", fg="white", dim=True
        ) + click.style(pfilename.name, fg="white", underline=False)

        click.echo(
            click.style(prettysize.rjust(6), fg="blue")
            + click.style(" | ", fg="red")
            + str(fancy_filename)
        )

        if real:
            ctx.unlink(filename)
            if verbose:
                click.echo(f"deleted: {filename}")
    click.echo("Total size: %s" % humanize(total_size))


def humanize(num: int) -> str:
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

    pretty = "%s %s" % (int(round(fnum, 0)), sym)
    return pretty


def walk_bottom_up(directory: str, video_types: set[str]) -> bool:
    """Walk a directory tree from the bottom up and return true
    if a video file is found."""
    is_empty = True
    for root, dirs, files in os.walk(directory, topdown=False):
        found_types = set()
        for file in files:
            abs_file: Path = Path(root, file)
            found_types.add(abs_file.suffix)
        if video_types.intersection(found_types):
            is_empty = False
    return is_empty
