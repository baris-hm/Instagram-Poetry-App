"""Refresh a long-lived Instagram token and rotate its Secret Manager version."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlencode

from .instagram_client import (
    InstagramAPIError,
    InstagramClient,
    Transport,
    urllib_transport,
)
from .settings import AppSettings

LOGGER = logging.getLogger(__name__)
SecretWriter = Callable[[str, bytes], str]


class TokenRefreshError(RuntimeError):
    """A sanitized token-rotation failure safe for application logs."""


@dataclass(frozen=True, slots=True)
class TokenRefreshResult:
    username: str
    secret_version: str
    expires_in: int


def refresh_long_lived_token(
    access_token: str,
    *,
    base_url: str = "https://graph.instagram.com",
    timeout: float = 30,
    transport: Transport = urllib_transport,
) -> tuple[str, int]:
    """Ask Meta to extend an unexpired long-lived token."""

    if not access_token:
        raise TokenRefreshError("Instagram access token is missing.")
    query = urlencode(
        {
            "grant_type": "ig_refresh_token",
            "access_token": access_token,
        }
    )
    response = transport(
        "GET",
        f"{base_url.rstrip('/')}/refresh_access_token?{query}",
        {
            "Accept": "application/json",
            "User-Agent": "Siirden-Karelere-Token-Refresh/0.4",
        },
        None,
        timeout,
    )
    refreshed_token = str(response.get("access_token") or "").strip()
    if not refreshed_token:
        raise TokenRefreshError("Instagram did not return a refreshed access token.")
    try:
        expires_in = int(response.get("expires_in") or 0)
    except (TypeError, ValueError) as error:
        raise TokenRefreshError("Instagram returned an invalid token lifetime.") from error
    if expires_in <= 0:
        raise TokenRefreshError("Instagram did not return a token lifetime.")
    return refreshed_token, expires_in


def add_secret_version(secret_resource: str, payload: bytes) -> str:
    """Store a new version and retain one previous token as a rollback."""

    try:
        from google.cloud import secretmanager
    except ImportError as error:  # pragma: no cover - deployment dependency guard
        raise TokenRefreshError("Secret Manager support is not installed.") from error

    try:
        client = secretmanager.SecretManagerServiceClient()
        response = client.add_secret_version(
            request={
                "parent": secret_resource,
                "payload": {"data": payload},
            }
        )
        active_versions = [
            item
            for item in client.list_secret_versions(request={"parent": secret_resource})
            if item.state != secretmanager.SecretVersion.State.DESTROYED
        ]
        active_versions.sort(
            key=lambda item: int(str(item.name).rsplit("/", maxsplit=1)[-1]),
            reverse=True,
        )
        for old_version in active_versions[2:]:
            client.destroy_secret_version(request={"name": old_version.name})
    except Exception as error:
        raise TokenRefreshError("The refreshed token could not be stored in Secret Manager.") from error
    version = str(response.name).rsplit("/", maxsplit=1)[-1]
    if not version:
        raise TokenRefreshError("Secret Manager did not return a version number.")
    return version


def refresh_validate_and_store(
    access_token: str,
    secret_resource: str,
    *,
    api_version: str = "v26.0",
    base_url: str = "https://graph.instagram.com",
    transport: Transport = urllib_transport,
    secret_writer: SecretWriter = add_secret_version,
) -> TokenRefreshResult:
    """Refresh, validate with ``/me``, then persist the replacement token."""

    if not secret_resource.startswith("projects/") or "/secrets/" not in secret_resource:
        raise TokenRefreshError("INSTAGRAM_SECRET_RESOURCE is invalid.")
    refreshed_token, expires_in = refresh_long_lived_token(
        access_token,
        base_url=base_url,
        transport=transport,
    )
    account = InstagramClient(
        refreshed_token,
        api_version=api_version,
        base_url=base_url,
        transport=transport,
    ).get_account()
    secret_version = secret_writer(secret_resource, refreshed_token.encode("utf-8"))
    return TokenRefreshResult(
        username=account.username,
        secret_version=secret_version,
        expires_in=expires_in,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = AppSettings.from_env()
    secret_resource = os.getenv("INSTAGRAM_SECRET_RESOURCE", "").strip()
    try:
        result = refresh_validate_and_store(
            settings.get_instagram_access_token(),
            secret_resource,
            api_version=settings.graph_api_version,
            base_url=settings.graph_api_base_url,
        )
    except (InstagramAPIError, TokenRefreshError, ValueError) as error:
        LOGGER.error("Instagram token refresh failed: %s", error)
        raise SystemExit(1) from error
    LOGGER.info(
        "Instagram token refreshed for @%s; stored Secret Manager version %s; expires in %s seconds.",
        result.username,
        result.secret_version,
        result.expires_in,
    )


if __name__ == "__main__":
    main()
