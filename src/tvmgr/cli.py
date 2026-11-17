"""CLI interface for tvmgr using Click."""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, cast

import click
from rich.markup import escape

from .completions import install_bash_completion
from .config import Config, ConfigError, config_path, load_config
from .discover import discover_kodi
from .kodi import KodiError, get_kodi_info, get_watched_media
from .tv_manager import (
    SmbUnavailableError,
    delete_files,
    sql,
    walk_bottom_up,
)
from .ui import Ui, make_ui

CONTEXT_SETTINGS = {"token_normalize_func": str.lower}


class _HelpOptions:
    """Give every command the same help option names."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        context_settings = dict(kwargs.pop("context_settings", {}) or {})
        context_settings.setdefault("help_option_names", ["-h", "--help"])
        super().__init__(*args, context_settings=context_settings, **kwargs)  # ty: ignore[unknown-argument]


class AppCommand(_HelpOptions, click.Command):
    """A leaf command with `-h` support."""


class AppGroup(_HelpOptions, click.Group):
    """A command group with `-h` support and shared command classes."""

    command_class = AppCommand
    group_class = type


@dataclass(frozen=True)
class AppContext:
    """Values shared by all subcommands."""

    config: Config
    ui: Ui


def config_callback(
    ctx: click.Context,
    _param: click.Parameter,
    value: bool,
) -> None:
    """Print the config path and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(config_path())
    ctx.exit()


def completions_callback(
    ctx: click.Context,
    _param: click.Parameter,
    value: bool,
) -> None:
    """Write bash completions and exit."""
    if not value or ctx.resilient_parsing:
        return
    install_bash_completion(
        cast(click.Group, ctx.command),
        ctx.info_name or "tvmgr",
        package_version("tvmgr"),
    )
    ctx.exit()


@click.group(
    "tvmgr",
    cls=AppGroup,
    no_args_is_help=True,
    context_settings=CONTEXT_SETTINGS,
)
@click.version_option(package_name="tvmgr", prog_name="tvmgr")
@click.option(
    "--color",
    type=click.Choice(["auto", "always", "never"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Control colored output.",
)
@click.option(
    "--config",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=config_callback,
    help="Print the config file path and exit.",
)
@click.option(
    "--completions",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=completions_callback,
    help="Write bash completions and exit.",
)
@click.pass_context
def main(ctx: click.Context, color: str) -> None:
    """Manage TV shows and movies on Kodi media centers."""
    try:
        config = load_config(warn=lambda message: click.echo(message, err=True))
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    ui = make_ui(color)
    ctx.color = {"always": True, "never": False, "auto": None}[color]
    ctx.obj = AppContext(config=config, ui=ui)


@main.command()
@click.argument("ip-address")
@click.option(
    "--real",
    is_flag=True,
    help="Delete files for real instead of listing them.",
)
@click.option("-v", "--verbose", is_flag=True, help="Give more information.")
@click.option(
    "--hide-deleted", is_flag=True, help="Don't display missing files."
)
@click.option(
    "-t/-m",
    "--tv/--movies",
    "is_tv",
    default=True,
    help="Delete tv shows or movies (default tv).",
)
@click.pass_obj
def viajson(
    app: AppContext,
    ip_address: str,
    real: bool,
    verbose: bool,
    hide_deleted: bool,
    is_tv: bool,
) -> None:
    """Delete using JSON-RPC and SMBC.

    Retrieve data from Kodi via its JSON API.

    JSON-RPC must be enabled. See https://kodi.wiki/view/JSON-RPC_API
    for details.

    HTTP: In System/Settings/Network/Services activate Allow control
    of Kodi via HTTP

    TCP: In settings > services > control activate "Allow programs
    on this system to control Kodi" for localhost access only and Allow
    programs on other systems to control Kodi for access from other
    computers as well

    \b
    To get the shield's ip address:
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
    try:
        file_names = get_watched_media(ip_address, is_tv, app.config)
        delete_files(
            file_names,
            hide_deleted,
            real,
            True,
            verbose,
            app.config,
            app.ui,
        )
    except (KodiError, SmbUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc


@main.command()
@click.argument(
    "kodi-database",
    type=click.Path(exists=True, resolve_path=True, path_type=Path),
)
@click.option(
    "--real",
    is_flag=True,
    help="Delete files for real instead of listing them.",
)
@click.option("-v", "--verbose", is_flag=True, help="Give more information.")
@click.option(
    "--hide-deleted", is_flag=True, help="Don't display missing files."
)
@click.option(
    "--smbc/--mount",
    "use_smbc",
    default=True,
    help="Access files via smbc or a mounted dir (default smbc).",
)
@click.pass_obj
def viadb(
    app: AppContext,
    kodi_database: Path,
    real: bool,
    verbose: bool,
    hide_deleted: bool,
    use_smbc: bool,
) -> None:
    """Delete using the Kodi database and SMBC.

    This program reads a kodi database and deletes the watched files
    listed if they are on an SMB share.

    It's recommended to run Kodi's "Clean library" in settings before
    reading the db. This will prevent "File does not exist" errors if
    some of the video files have been manually deleted.

    KODI-DATABASE - The location of the kodi userdata video db. The db
    filename changes on xbmc upgrades, and will look like
    myVideos60.db or myVideos20.db etc... Use the highest numbered one.

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
    connection = sqlite3.connect(str(kodi_database))
    try:
        cursor = connection.cursor()
        data = cursor.execute(sql)
        try:
            delete_files(
                data,
                hide_deleted,
                real,
                use_smbc,
                verbose,
                app.config,
                app.ui,
            )
        except SmbUnavailableError as exc:
            raise click.ClickException(str(exc)) from exc
    finally:
        connection.close()


@main.command()
@click.argument(
    "roots",
    type=click.Path(exists=True, path_type=Path),
    nargs=-1,
)
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
@click.pass_obj
def cleanup(
    app: AppContext,
    roots: tuple[Path, ...],
    show: str,
    null_terminate: bool,
) -> None:
    """List dirs that do or don't have any video files in them.

    \b
    To show the contents of empty dirs:
      while read line; do
        tree "$line";
      done < <(tvmgr cleanup --show=e *) | less

    \b
    To delete the empty dirs:
      while read file; do
        echo trash "$file";
      done < <(tvmgr cleanup --show=e *)

    \b
    To see a list of used file types in a directory tree.
    All dirs:
      find -type f -exec basename {} \\; | sed 's/^.*\\.//' | sort | uniq -c | sort -n

    \b
    Show dirs with no video files:
      tvmgr cleanup --show=e * --null \\
      | xargs -0 -I"@" find "@" -type f -exec basename {} \\; \\
      | sed 's/^.*\\.//' \\
      | sort \\
      | uniq -c

    \b
    To see the total size of all the dirs with no video files:
      tvmgr cleanup --show=e * --null | xargs -0 du -hsc | tail -n 1
    """
    video_files = {
        ".mp4",
        ".mkv",
        ".avi",
        ".mpg",
        ".mpeg",
        ".mov",
        ".flv",
        ".wmv",
        ".iso",
    }
    for root in roots:
        is_empty = walk_bottom_up(str(root), video_types=video_files)
        if is_empty and show in ["e", "b"]:
            _print_cleanup_path(app.ui, root, null_terminate, "red")
        elif not is_empty and show in ["f", "b"]:
            _print_cleanup_path(app.ui, root, null_terminate, "green")


def _print_cleanup_path(
    ui: Ui,
    root: Path,
    null_terminate: bool,
    color: str,
) -> None:
    if null_terminate:
        sys.stdout.write(f"{root}\0")
    else:
        ui.out.print(f"[{color}]{escape(str(root))}[/{color}]", soft_wrap=True)


@main.command()
@click.option(
    "--network",
    multiple=True,
    help=(
        "Network to scan in CIDR notation. Can be specified multiple "
        "times. Defaults to [discover] networks in the config file."
    ),
)
@click.option(
    "--timeout",
    default=None,
    type=float,
    help=(
        "Timeout for connection attempts in seconds. Defaults to "
        "[discover] timeout in the config file."
    ),
)
@click.pass_obj
def discover(
    app: AppContext,
    network: tuple[str, ...],
    timeout: float | None,
) -> None:
    """Discover Kodi devices on the network.

    Scans the specified network(s) for devices running Kodi and displays
    detailed information about each device found, including system info,
    library statistics, and current playback status.

    By default, scans the networks listed under [discover] in the config
    file.

    \b
    Examples:
      tvmgr discover
      tvmgr discover --network 192.168.0.0/24
      tvmgr discover --network 192.168.0.0/24 --network 192.168.1.0/24
      tvmgr discover --network 10.0.0.0/24 --timeout 1.0
    """
    networks = list(network) if network else list(app.config.discover.networks)
    scan_timeout = (
        timeout if timeout is not None else app.config.discover.timeout
    )
    network_str = ", ".join(networks)

    app.ui.out.print(f"Scanning {escape(network_str)} for Kodi devices...")
    app.ui.out.print()

    devices = discover_kodi(networks, scan_timeout)

    if not devices:
        app.ui.out.print(
            "[yellow]No Kodi devices found on the network.[/yellow]"
        )
        return

    app.ui.out.print(f"[green]Found {len(devices)} Kodi device(s):[/green]\n")

    for ip in devices:
        app.ui.out.print(f"[cyan bold]Device: {escape(ip)}[/cyan bold]")
        info = get_kodi_info(ip, app.config)

        system = info.get("system")
        if isinstance(system, dict):
            app.ui.out.print("\n[blue bold]System Information:[/blue bold]")
            name = escape(str(system.get("name", "Unknown")))
            version = escape(str(system.get("version", "Unknown")))
            volume = escape(str(system.get("volume", 0)))
            url = escape(str(info["url"]))
            app.ui.out.print(f"  Name:    {name}")
            app.ui.out.print(f"  Version: {version}")
            app.ui.out.print(f"  Volume:  {volume}%")
            app.ui.out.print(f"  URL:     {url}")

        library = info.get("library")
        if isinstance(library, dict):
            app.ui.out.print("\n[blue bold]Library Statistics:[/blue bold]")
            tv_shows = escape(str(library.get("tv_shows", 0)))
            episodes = escape(str(library.get("episodes", 0)))
            movies = escape(str(library.get("movies", 0)))
            app.ui.out.print(f"  TV Shows: {tv_shows}")
            app.ui.out.print(f"  Episodes: {episodes}")
            app.ui.out.print(f"  Movies:   {movies}")

        player = info.get("player")
        if isinstance(player, dict):
            app.ui.out.print("\n[blue bold]Player Status:[/blue bold]")
            if player.get("active"):
                playing = escape(str(player.get("playing", "Unknown")))
                media_type = escape(str(player.get("type", "unknown")))
                app.ui.out.print(f"  Playing: {playing} ({media_type})")
            else:
                app.ui.out.print("  Status:  Idle")

        addons = info.get("addons")
        if isinstance(addons, dict):
            app.ui.out.print("\n[blue bold]Add-ons:[/blue bold]")
            video_addons = escape(str(addons.get("video_addons", 0)))
            app.ui.out.print(f"  Video Add-ons: {video_addons}")

        error = info.get("error")
        if error:
            app.ui.out.print(
                f"\n[red]Error gathering info: {escape(str(error))}[/red]"
            )

        app.ui.out.print()
