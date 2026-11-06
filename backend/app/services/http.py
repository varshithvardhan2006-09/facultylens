"""Shared outbound HTTP for profile imports: timeouts, polite retries, readable failures."""

import asyncio
import email.utils
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import get_settings

USER_AGENT = "FacultyLens/0.2 (college faculty profile import; mailto unset)"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


class ExternalServiceError(Exception):
    """An import source failed. `status` is what the API should answer (404, 429 or 502)."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message = message
        self.status = status


def _retry_after(response: httpx.Response, attempt: int) -> float:
    value = response.headers.get("retry-after")
    if value:
        if value.isdigit():
            return min(float(value), 10.0)
        try:
            when = email.utils.parsedate_to_datetime(value)
            return max(0.0, min((when - datetime.now(UTC)).total_seconds(), 10.0))
        except (TypeError, ValueError):
            pass
    return min(1.5 * 2**attempt, 8.0)


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    source: str,
    **kwargs: Any,
) -> Any:
    """Send a request with up to 3 attempts on 429/5xx/network errors; return parsed JSON.

    404 raises ExternalServiceError(status=404); an exhausted 429 raises status=429; anything
    else that fails raises status=502. Callers turn these into plain HTTP errors.
    """
    last: str = ""
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = await client.request(method, url, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = f"{source} didn't answer ({type(exc).__name__})."
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
                continue
            raise ExternalServiceError(f"{last} Try again in a minute.") from None
        if response.status_code == 404:
            raise ExternalServiceError(f"{source} has no record for that ID.", status=404)
        if response.status_code in RETRY_STATUSES:
            last = f"{source} answered {response.status_code}."
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(_retry_after(response, attempt))
                continue
            if response.status_code == 429:
                raise ExternalServiceError(
                    f"{source} is limiting requests right now. Wait a minute and try again.",
                    status=429,
                )
            raise ExternalServiceError(f"{last} Try again in a minute.")
        if response.status_code >= 400:
            raise ExternalServiceError(f"{source} refused the request ({response.status_code}).")
        try:
            return response.json()
        except ValueError:
            raise ExternalServiceError(f"{source} sent a response we couldn't read.") from None
    raise ExternalServiceError(last or f"{source} failed.")


def make_client(**headers: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=get_settings().import_timeout_seconds,
        headers={"User-Agent": USER_AGENT, **headers},
        follow_redirects=True,
    )
