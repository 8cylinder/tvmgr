#!/usr/bin/env python3

"""CLI interface for tvmgr using Click."""

import sys
import json
import sqlite3
import click
from pathlib import Path
import requests

from .tv_manager import (
    delete_files,
    walk_bottom_up,
    sql,
)
from .discover import (
    discover_kodi,
    get_kodi_info,
)

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "token_normalize_func": lambda x: x.lower(),
}


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


@main.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--network",
    multiple=True,
    help="Network to scan in CIDR notation. Can be specified multiple times. Default: 192.168.0.0/24 and 192.168.1.0/24",
)
@click.option(
    "--timeout",
    default=0.5,
    type=float,
    help="Timeout for connection attempts in seconds (default: 0.5).",
)
def discover(network: tuple[str], timeout: float) -> None:
    """Discover Kodi devices on the network.

    Scans the specified network(s) for devices running Kodi and displays
    detailed information about each device found, including system info,
    library statistics, and current playback status.

    By default, scans 192.168.0.0/24 and 192.168.1.0/24.

    \b
    Examples:
      tvmgr discover
      tvmgr discover --network 192.168.0.0/24
      tvmgr discover --network 192.168.0.0/24 --network 192.168.1.0/24
      tvmgr discover --network 10.0.0.0/24 --timeout 1.0
    """

    # Convert tuple to list, or use None for defaults
    networks = list(network) if network else None

    # Display which networks are being scanned
    if networks:
        network_str = ", ".join(networks)
    else:
        network_str = "192.168.0.0/24, 192.168.1.0/24"

    click.echo(f"Scanning {network_str} for Kodi devices...")
    click.echo()

    devices = discover_kodi(networks, timeout)

    if not devices:
        click.secho("No Kodi devices found on the network.", fg="yellow")
        return

    click.secho(f"Found {len(devices)} Kodi device(s):\n", fg="green", bold=True)

    for ip in devices:
        click.echo(click.style(f"Device: {ip}", fg="cyan", bold=True))

        info = get_kodi_info(ip)

        # Display system information
        if info.get("system"):
            sys_info = info["system"]
            click.echo(click.style("\nSystem Information:", fg="blue", bold=True))
            click.echo(f"  Name:    {sys_info.get('name', 'Unknown')}")
            click.echo(f"  Version: {sys_info.get('version', 'Unknown')}")
            click.echo(f"  Volume:  {sys_info.get('volume', 0)}%")
            click.echo(f"  URL:     {info['url']}")

        # Display library statistics
        if info.get("library"):
            lib_info = info["library"]
            click.echo(click.style("\nLibrary Statistics:", fg="blue", bold=True))
            click.echo(f"  TV Shows: {lib_info.get('tv_shows', 0)}")
            click.echo(f"  Episodes: {lib_info.get('episodes', 0)}")
            click.echo(f"  Movies:   {lib_info.get('movies', 0)}")

        # Display player status
        if info.get("player"):
            player_info = info["player"]
            click.echo(click.style("\nPlayer Status:", fg="blue", bold=True))
            if player_info.get("active"):
                click.echo(
                    f"  Playing: {player_info.get('playing', 'Unknown')} "
                    f"({player_info.get('type', 'unknown')})"
                )
            else:
                click.echo("  Status:  Idle")

        # Display add-ons info
        if info.get("addons"):
            addons_info = info["addons"]
            click.echo(click.style("\nAdd-ons:", fg="blue", bold=True))
            click.echo(f"  Video Add-ons: {addons_info.get('video_addons', 0)}")

        # Display any errors
        if info.get("error"):
            click.echo(
                click.style(f"\nError gathering info: {info['error']}", fg="red")
            )

        click.echo()
