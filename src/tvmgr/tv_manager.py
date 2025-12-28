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
        Probably: sudo apt install build-essential pkg-config smbcclient libsmbclient libsmbclient-dev python3-dev
        and/or: pip3 install pysmbc,
        or best yet: sudo apt install python3-pysmbc or python3-smbc""")
    exit()

import click
import logging as l
from pathlib import Path
from urllib.parse import urlparse

# set up logging -- eg: l.error('This is an error')
this_file = __file__
log_file = "{}.log".format(this_file)
l.basicConfig(format="%(asctime)s -- %(levelname)s -- %(message)s", filename=log_file)

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "token_normalize_func": lambda x: x.lower(),
}

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


@click.group(context_settings=CONTEXT_SETTINGS)
def main() -> None:
    pass


@main.command(context_settings=CONTEXT_SETTINGS)
@click.argument("ip-address")
@click.option(
    "--real", is_flag=True, help="Delete files for real instead of listing them."
)
@click.option("-v", "--verbose", is_flag=True, help="Give more information.")
@click.option("--hide-deleted", is_flag=True, help="Don't display missing files.")
# @click.option(
#     "--smbc/--mount",
#     "use_smbc",
#     default=True,
#     help="Access files via smbc or a mounted dir (default smbc).",
# )
@click.option(
    "-t/-m",
    "--tv/--movies",
    "is_tv",
    default=True,
    help="Delete tv shows or movies (default tv).",
)
def viajson(
    ip_address: str,
    real: bool,
    verbose: bool,
    hide_deleted: bool,
    # use_smbc: bool,
    is_tv: bool,
) -> None:
    """Delete using JSON-RCP and SMBC.

    Retrieve data from Kodi via it's json api.

    JSON-RCP must be enabled.  See https://kodi.wiki/view/JSON-RPC_API
    for details.

    HTTP: In System/Settings/Network/Services activate Allow control
    of Kodi via HTTP

    TCP: In settings > services > control activate "Allow programs
    on this system to control Kodi" for localhost access only and Allow
    programs on other systems to control Kodi for access from other
    computers as well

    settings/services/control: xxx

    \b
    To get the sheild's ip address:
    Settings > Device preferences > About > status > Ip address

    \b
    Kodi defaults:
      ip: 192.168.0.28
      port: 8080
      username: kodi
      password: <none>

    \b
    SMBC defaults:
      username: sm
      password: Password123
    """

    endpoint = f"http://{ip_address}:8080/jsonrpc"
    media_type = "tv" if is_tv else "movies"
    media_types = {
        "tv": [
            "VideoLibrary.GetEpisodes",
            "showtitle",
            "episodes",
            "showtitle",
        ],
        "movies": [
            "VideoLibrary.GetMovies",
            "originaltitle",
            "movies",
            "originaltitle",
        ],
    }

    kodi_data = {
        "jsonrpc": "2.0",
        "method": media_types[media_type][0],
        "params": {
            "properties": [
                media_types[media_type][1],
                "file",
            ],
            "filter": {
                "field": "playcount",
                "operator": "greaterthan",
                "value": "0",
            },
        },
        "id": "get-watched-episodes",
    }
    kodi_json = json.dumps(kodi_data)
    payload = {"request": kodi_json}

    try:
        r = requests.get(endpoint, payload)
    except requests.exceptions.ConnectionError:
        print(f"url: {endpoint}")
        sys.exit("Network is unreachable")

    result = r.json()

    episodes = result["result"][media_types[media_type][2]]

    file_names = [(i["file"], i[media_types[media_type][3]]) for i in episodes]
    use_smbc = True
    delete_files(file_names, hide_deleted, real, use_smbc, verbose)


@main.command(context_settings=CONTEXT_SETTINGS)
@click.argument("kodi-database", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--real", is_flag=True, help="Delete files for real instead of listing them."
)
@click.option("-v", "--verbose", is_flag=True, help="Give more information.")
@click.option("--hide-deleted", is_flag=True, help="Don't display missing files.")
@click.option(
    "--smbc/--mount",
    "use_smbc",
    default=True,
    help="Access files via smbc or a mounted dir (default smbc).",
)
def viadb(
    kodi_database: Path, real: bool, verbose: bool, hide_deleted: bool, use_smbc: bool
) -> None:
    """Delete using the Kodi db and SMBC.

    This program reads a kodi database and deletes the watched files
    listed, if they are on an SMB share.

    Its recomended to run Kodi's "Clean library" in settings before
    reading the db.  This will prevent "File does not exist" errors if
    some of the video files have been manualy deleted.

    KODI-DATABASE - The location of the kodi userdata video db. The db
    filename changes on xbmc upgrades, and will look like
    myVideos60.db or myVideos20.db etc...  Use the highest numbered one.

    \b
    The location of the kodi db:
    Linux     | ~/.kodi/userdata/
    Android   | Android/data/org.xbmc.kodi/files/.kodi/userdata/
    Windows   | %APPDATA%/kodi/userdata
    Windows   | /Users/%username%/Application Data/XBMC/userdata/Database/
    Mac       | ~/Library/Application Support/Kodi/userdata/
    iOS       | /private/var/mobile/Library/Preferences/Kodi/userdata/
    LibreELEC | /storage/.kodi/userdata/
    """

    conn = sqlite3.connect(kodi_database)
    curs = conn.cursor()
    data = curs.execute(sql)
    delete_files(data, hide_deleted, real, use_smbc, verbose)


@main.command(context_settings=CONTEXT_SETTINGS)
@click.argument("roots", type=click.Path(exists=True), nargs=-1)
@click.option(
    "--null",
    "-0",
    "null_terminate",
    is_flag=True,
    help="Use the null character as a delimiter.",
)
@click.option(
    "--show",
    "-s",
    type=click.Choice(["e", "f", "b"]),
    default="e",
    help="Show (e)mpty dirs, (f)ull dirs, or (b)oth.",
)
def cleanup(roots: list[Path], show: str, null_terminate: bool) -> None:
    """list dirs that do or don't have any video files in them.

    \b
    To see a list of used file types in a directory tree.
    All dirs:
      find -type f -exec basename {} \\; | sed 's/^.*\\.//' | sort | uniq -c | sort -n
    Dirs with no video files:
      tv--delete-watched-shows cleanup --show=e * --null \\
      | xargs -0 -I"@" find "@" -type f -exec basename {} \\; \\
      | sed 's/^.*\\.//' \\
      | sort \\
      | uniq -c

    \b
    To see the total size of all the dirs with no video files:
      tv--delete-watched-shows cleanup --show=e * --null | xargs -0 du -hsc | tail -n 1

    \b
    To show the contents of empty dirs:
      while read line; do
        tree "$line";
      done < <(tv--delete-watched-shows cleanup --show=e *) | less

    \b
    To delete the empty dirs:
      while read file; do
        echo trash "$file";
      done < <(tv--delete-watched-shows cleanup --show=e *)
    """

    end = "\0" if null_terminate else "\n"

    video_files = [
        ".mp4",
        ".mkv",
        ".avi",
        ".mpg",
        ".mpeg",
        ".mov",
        ".flv",
        ".wmv",
        ".iso",
    ]
    for root in roots:
        if walk_bottom_up(str(root), video_types=set(video_files)):
            if show in ["e", "b"]:
                click.secho(f"{root}{end}", fg="red", nl=False)
        else:
            if show in ["f", "b"]:
                click.secho(f"{root}{end}", fg="green", nl=False)


if __name__ == "__main__":
    main()
