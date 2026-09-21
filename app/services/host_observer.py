"""Client for the private, device-local Host Observer API."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8200/api/v1"


class HostObserverUnavailable(RuntimeError):
    """Raised when the dashboard cannot obtain a trusted host snapshot."""


def _base_url() -> str:
    configured = os.getenv("HOST_OBSERVER_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(configured)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HostObserverUnavailable("The Host Observer URL is not configured correctly.")
    return configured


def get_snapshot() -> dict[str, Any]:
    """Fetch the normalized host snapshot; never inspect another device directly."""

    try:
        timeout = float(os.getenv("HOST_OBSERVER_TIMEOUT_SECONDS", "3"))
        request = Request(f"{_base_url()}/host", headers={"Accept": "application/json"})
        with urlopen(request, timeout=max(timeout, 0.1)) as response:
            snapshot = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        raise HostObserverUnavailable(
            "The private Host Observer is unavailable. Start it on the device being monitored."
        ) from error

    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "1":
        raise HostObserverUnavailable("The Host Observer returned an unsupported response.")
    return snapshot
