"""Device-neutral host observation primitives used by the private Host Observer."""

from __future__ import annotations

import json
import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil


def _service_aliases() -> dict[str, str]:
    """Read optional, per-device port aliases without baking them into the code."""

    try:
        configured = json.loads(os.getenv("HOST_OBSERVER_SERVICE_LABELS", "{}"))
    except json.JSONDecodeError:
        return {}
    return {
        str(port): str(label).strip()
        for port, label in configured.items()
        if str(label).strip()
    } if isinstance(configured, dict) else {}


def _listener_scope(address: str) -> str:
    return "Local only" if address in {"127.0.0.1", "::1"} else "Network listener"


def _disk_path() -> str:
    home = Path.home()
    if home.exists():
        return str(home)
    return str(Path("/"))


def _process_name(pid: int | None) -> str:
    if pid is None:
        return "Unknown process"
    try:
        return psutil.Process(pid).name()
    except (psutil.Error, OSError):
        return "Unknown process"


def listening_services() -> list[dict[str, Any]]:
    """Normalize listening TCP sockets from Windows, Linux, or Raspberry Pi OS."""

    aliases = _service_aliases()
    services: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int | None]] = set()
    try:
        connections = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, psutil.Error, OSError):
        connections = []

    for connection in connections:
        if connection.status != psutil.CONN_LISTEN or not connection.laddr:
            continue
        address, port = connection.laddr[0], connection.laddr[1]
        key = (address, port, connection.pid)
        if key in seen:
            continue
        seen.add(key)
        process_name = _process_name(connection.pid)
        services.append(
            {
                "name": aliases.get(str(port), process_name),
                "process": process_name,
                "port": port,
                "address": address,
                "scope": _listener_scope(address),
                "pid": connection.pid,
            }
        )

    return sorted(
        services,
        key=lambda service: (
            service["scope"] != "Local only",
            service["port"],
            service["name"].lower(),
        ),
    )


def host_snapshot() -> dict[str, Any]:
    """Return the versioned API contract consumed by the dashboard Homelab tab."""

    disk = psutil.disk_usage(_disk_path())
    services = listening_services()
    return {
        "schema_version": "1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": socket.gethostname() or "localhost",
            "platform": platform.system() or "Unknown",
            "cpu_percent": round(psutil.cpu_percent(interval=0.05), 1),
            "memory_percent": round(psutil.virtual_memory().percent, 1),
            "disk_percent": round(disk.percent, 1),
        },
        "services": services,
        "summary": {
            "total_listeners": len(services),
            "local_only": sum(service["scope"] == "Local only" for service in services),
            "network_listeners": sum(
                service["scope"] == "Network listener" for service in services
            ),
        },
    }
