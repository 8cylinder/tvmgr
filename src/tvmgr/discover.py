"""Network discovery module for finding Kodi devices."""

from __future__ import annotations

import ipaddress
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests


def discover_kodi(
    networks: list[str] | str,
    timeout: float = 0.5,
) -> list[str]:
    """Scan one or more networks for Kodi devices."""
    if isinstance(networks, str):
        networks = [networks]

    def check_kodi(ip: ipaddress.IPv4Address) -> str | None:
        """Check if a single IP has Kodi running on its JSON-RPC port."""
        ip_str = str(ip)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            if sock.connect_ex((ip_str, 8080)) == 0:
                try:
                    resp = requests.post(
                        f"http://{ip_str}:8080/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "JSONRPC.Ping",
                            "id": 1,
                        },
                        timeout=2,
                    )
                    if resp.json().get("result") == "pong":
                        return ip_str
                except Exception:  # noqa: BLE001, S110
                    pass
        finally:
            sock.close()

        return None

    network_ips: list[ipaddress.IPv4Address] = []
    for network in networks:
        network_ips.extend(ipaddress.IPv4Network(network))

    kodi_devices: list[str] = []

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_kodi, ip): ip for ip in network_ips}

        for future in as_completed(futures):
            result = future.result()
            if result:
                kodi_devices.append(result)

    return kodi_devices
