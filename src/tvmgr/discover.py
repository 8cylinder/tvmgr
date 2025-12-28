#!/usr/bin/env python3

"""Network discovery module for finding and querying Kodi devices."""

import socket
import requests
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional


def discover_kodi(networks: list[str] | str = None, timeout: float = 0.5) -> list[str]:
    """
    Scan network(s) for Kodi devices.

    Args:
        networks: Network(s) to scan in CIDR notation. Can be a single string
                 or list of strings (e.g., "192.168.1.0/24" or
                 ["192.168.0.0/24", "192.168.1.0/24"]).
                 Defaults to ["192.168.0.0/24", "192.168.1.0/24"]
        timeout: Socket timeout in seconds for port check

    Returns:
        List of IP addresses where Kodi was found
    """

    # Set default networks if none provided
    if networks is None:
        networks = ["192.168.0.0/24", "192.168.1.0/24"]

    # Convert single network string to list
    if isinstance(networks, str):
        networks = [networks]

    def check_kodi(ip):
        """Check if a single IP has Kodi running on port 8080."""
        ip_str = str(ip)

        # Quick port check
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            if sock.connect_ex((ip_str, 8080)) == 0:
                # Port is open, verify it's Kodi with JSON-RPC ping
                try:
                    resp = requests.post(
                        f"http://{ip_str}:8080/jsonrpc",
                        json={"jsonrpc": "2.0", "method": "JSONRPC.Ping", "id": 1},
                        timeout=2,
                    )
                    if resp.json().get("result") == "pong":
                        return ip_str
                except Exception:
                    pass
        finally:
            sock.close()

        return None

    # Collect all IPs from all networks
    network_ips = []
    for network in networks:
        network_ips.extend(list(ipaddress.IPv4Network(network)))

    kodi_devices = []

    # Scan network in parallel for speed
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_kodi, ip): ip for ip in network_ips}

        for future in as_completed(futures):
            result = future.result()
            if result:
                kodi_devices.append(result)

    return kodi_devices


def get_kodi_info(ip: str) -> dict:
    """
    Gather comprehensive information about a Kodi device.

    Args:
        ip: IP address of the Kodi device

    Returns:
        Dictionary with all available Kodi information
    """
    info = {
        "ip": ip,
        "url": f"http://{ip}:8080",
        "system": {},
        "library": {},
        "player": {},
        "addons": {},
    }

    try:
        # Get system properties
        system_props = _query_kodi(
            ip,
            "System.GetProperties",
            {
                "properties": [
                    "canshutdown",
                    "cansuspend",
                    "canhibernate",
                    "canreboot",
                    "volume",
                    "name",
                    "version",
                ]
            },
        )

        if system_props:
            info["system"] = {
                "name": system_props.get("name", "Unknown"),
                "version": _format_version(system_props.get("version", {})),
                "volume": system_props.get("volume", 0),
                "can_shutdown": system_props.get("canshutdown", False),
                "can_suspend": system_props.get("cansuspend", False),
                "can_hibernate": system_props.get("canhibernate", False),
                "can_reboot": system_props.get("canreboot", False),
            }

        # Get library statistics
        tv_shows = _query_kodi(ip, "VideoLibrary.GetTVShows", {})
        movies = _query_kodi(ip, "VideoLibrary.GetMovies", {})
        episodes = _query_kodi(ip, "VideoLibrary.GetEpisodes", {})

        info["library"] = {
            "tv_shows": len(tv_shows.get("tvshows", [])) if tv_shows else 0,
            "movies": len(movies.get("movies", [])) if movies else 0,
            "episodes": len(episodes.get("episodes", [])) if episodes else 0,
        }

        # Get active players
        active_players = _query_kodi(ip, "Player.GetActivePlayers", {})
        if active_players and len(active_players) > 0:
            player_id = active_players[0].get("playerid")
            player_item = _query_kodi(
                ip, "Player.GetItem", {"playerid": player_id, "properties": ["title"]}
            )
            info["player"] = {
                "active": True,
                "type": active_players[0].get("type", "unknown"),
                "playing": player_item.get("item", {}).get("title", "Unknown")
                if player_item
                else "Unknown",
            }
        else:
            info["player"] = {"active": False}

        # Get enabled add-ons count
        addons = _query_kodi(
            ip, "Addons.GetAddons", {"enabled": True, "type": "xbmc.addon.video"}
        )
        info["addons"] = {
            "video_addons": len(addons.get("addons", [])) if addons else 0
        }

    except Exception as e:
        info["error"] = str(e)

    return info


def _query_kodi(ip: str, method: str, params: dict, timeout: int = 3) -> Optional[dict]:
    """
    Send a JSON-RPC request to Kodi and return the result.

    Args:
        ip: IP address of Kodi device
        method: JSON-RPC method name
        params: Parameters for the method
        timeout: Request timeout in seconds

    Returns:
        Result dictionary from Kodi, or None if request failed
    """
    try:
        response = requests.post(
            f"http://{ip}:8080/jsonrpc",
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=timeout,
        )
        result = response.json()
        return result.get("result")
    except Exception:
        return None


def _format_version(version_dict: dict) -> str:
    """
    Format Kodi version dictionary into a readable string.

    Args:
        version_dict: Version info from Kodi (major, minor, revision, tag)

    Returns:
        Formatted version string (e.g., "20.2 Nexus")
    """
    if not version_dict:
        return "Unknown"

    major = version_dict.get("major", "?")
    minor = version_dict.get("minor", 0)
    tag = version_dict.get("tag", "")

    if tag:
        return f"{major}.{minor} {tag}"
    return f"{major}.{minor}"
