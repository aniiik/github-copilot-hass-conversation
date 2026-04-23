"""Shared utilities for the GitHub Copilot Conversation integration."""

from __future__ import annotations

import logging

import aiohttp

from .const import COPILOT_API_BASE

_LOGGER = logging.getLogger(__name__)


async def async_fetch_models(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> list[str]:
    """Fetch available chat models from the Copilot API.

    Returns a sorted, deduplicated list of model family names.
    """
    try:
        async with session.get(
            f"{COPILOT_API_BASE}/models",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                _LOGGER.error(
                    "Copilot /models returned %s, using fallback",
                    resp.status,
                )
                raise ValueError(f"Copilot /models returned {resp.status}")
            data = await resp.json()
    except aiohttp.ClientError as err:
        _LOGGER.error("Failed to fetch models: %s", err)
        raise ValueError(f"Failed to fetch models: {err}") from err

    all_models: list[dict] = data.get("data", [])
    chat_models = []
    for model in all_models:
        capabilities = model.get("capabilities", {})
        if capabilities.get("type") == "chat":
            chat_models.append(capabilities.get("family", ""))

    if not chat_models:
        raise ValueError("No chat models available")

    # Remove duplicates while preserving order, then sort
    chat_models = list(dict.fromkeys(chat_models))
    chat_models.sort()
    return chat_models
