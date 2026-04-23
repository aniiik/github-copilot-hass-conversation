"""The GitHub Copilot Conversation integration."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_GITHUB_TOKEN,
    COPILOT_API_BASE,
    COPILOT_HEADERS,
    COPILOT_TOKEN_URL,
    DOMAIN,
    EXCHANGEABLE_TOKEN_PREFIXES,
    TOKEN_REFRESH_BUFFER_SECS,
)
from .utils import async_fetch_models

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["conversation"]


def _is_exchangeable(token: str) -> bool:
    """Return True if the token is a GitHub PAT that can be exchanged."""
    return token.startswith(EXCHANGEABLE_TOKEN_PREFIXES)


async def async_exchange_copilot_token(
    session: aiohttp.ClientSession,
    github_token: str,
) -> tuple[str, float | None]:
    """Exchange a GitHub PAT for a short-lived Copilot API token.

    Returns:
        (copilot_token, expires_at_unix_timestamp)

    Raises:
        ConfigEntryAuthFailed on 401 (invalid PAT or no Copilot subscription).
        ConfigEntryNotReady on connection / server errors.
    """
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/json",
        **COPILOT_HEADERS,
    }
    try:
        async with session.get(
            COPILOT_TOKEN_URL,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status in (401, 403):
                body = await resp.text()
                _LOGGER.error(
                    "Copilot token exchange failed (%s): %s",
                    resp.status,
                    body,
                )
                raise ConfigEntryAuthFailed(
                    f"GitHub Copilot token exchange failed ({resp.status}). "
                    "Check that your GitHub token has the 'copilot' scope "
                    "and you have an active Copilot subscription."
                )
            if resp.status != 200:
                body = await resp.text()
                raise ConfigEntryNotReady(
                    f"GitHub Copilot token exchange failed ({resp.status}): {body}"
                )
            data = await resp.json()
            token = data.get("token")
            if not token:
                raise ConfigEntryNotReady(
                    "GitHub Copilot token exchange returned empty token"
                )
            expires_at = data.get("expires_at")
            return token, float(expires_at) if expires_at else None

    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(f"Cannot connect to GitHub: {err}") from err


@dataclass
class CopilotRuntimeData:
    """Shared runtime data for a config entry."""

    session: aiohttp.ClientSession
    github_token: str
    copilot_token: str = ""
    expires_at: float | None = None
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def get_headers(self) -> dict[str, str]:
        """Return the authorization + Copilot headers for API calls."""
        return {
            "Authorization": f"Bearer {self.copilot_token}",
            "Content-Type": "application/json",
            **COPILOT_HEADERS,
        }

    def is_token_expiring(self) -> bool:
        """Return True if the Copilot token is near or past expiry."""
        if self.expires_at is None:
            return False
        return time.time() >= self.expires_at - TOKEN_REFRESH_BUFFER_SECS

    async def async_ensure_token(self) -> None:
        """Refresh the Copilot token if it is near expiry.

        Thread-safe via asyncio.Lock to prevent concurrent refreshes.
        """
        if not self.is_token_expiring():
            return

        async with self._refresh_lock:
            # Double-check after acquiring lock
            if not self.is_token_expiring():
                return

            if not _is_exchangeable(self.github_token):
                _LOGGER.warning(
                    "Cannot refresh Copilot token: GitHub token is not exchangeable"
                )
                return

            _LOGGER.debug("Copilot token near/past expiry — refreshing")
            try:
                new_token, expires_at = await async_exchange_copilot_token(
                    self.session, self.github_token
                )
                self.copilot_token = new_token
                self.expires_at = expires_at
                _LOGGER.debug("Copilot token refreshed successfully")
            except Exception:
                _LOGGER.exception("Failed to refresh Copilot token")

    async def async_refresh_on_401(self) -> bool:
        """Force-refresh the Copilot token after a 401.

        Returns True if refresh was successful.
        """
        async with self._refresh_lock:
            if not _is_exchangeable(self.github_token):
                return False
            try:
                new_token, expires_at = await async_exchange_copilot_token(
                    self.session, self.github_token
                )
                self.copilot_token = new_token
                self.expires_at = expires_at
                return True
            except Exception:
                _LOGGER.exception("Failed to refresh Copilot token after 401")
                return False

    async def async_get_available_models(self) -> list[str]:
        return await async_fetch_models(self.session, self.get_headers())


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up GitHub Copilot Conversation from a config entry."""
    github_token = entry.data[CONF_GITHUB_TOKEN]
    session = async_get_clientsession(hass)

    # Exchange GitHub PAT for a Copilot token (validates both PAT and subscription)
    copilot_token, expires_at = await async_exchange_copilot_token(
        session, github_token
    )

    runtime = CopilotRuntimeData(
        session=session,
        github_token=github_token,
        copilot_token=copilot_token,
        expires_at=expires_at,
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
