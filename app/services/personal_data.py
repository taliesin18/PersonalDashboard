"""Small, server-side client for the Personal Data Layer read API."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8100/api/v1"


class PersonalDataLayerUnavailable(RuntimeError):
    """Raised when the dashboard cannot safely read the shared service."""


def base_url() -> str:
    configured = os.getenv("PERSONAL_DATA_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlparse(configured)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise PersonalDataLayerUnavailable("The Personal Data Layer URL is not configured correctly.")
    return configured


def get_records(endpoint: str, params: dict[str, str | int] | None = None) -> list[dict[str, Any]]:
    """Read one collection from the approved API, never from its database file."""

    query = urlencode(params or {})
    url = f"{base_url()}/{endpoint.lstrip('/')}" + (f"?{query}" if query else "")
    try:
        timeout = float(os.getenv("PERSONAL_DATA_TIMEOUT_SECONDS", "3"))
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=max(timeout, 0.1)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        raise PersonalDataLayerUnavailable(
            "The Personal Data Layer is unavailable. Start its local API and check the dashboard connection setting."
        ) from error

    if not isinstance(payload, list):
        raise PersonalDataLayerUnavailable("The Personal Data Layer returned an unexpected response.")
    return [record for record in payload if isinstance(record, dict)]
