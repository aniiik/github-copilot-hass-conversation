"""Config flow for GitHub Copilot Conversation."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import llm, selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CONTINUE_CONVERSATION,
    CONF_GITHUB_TOKEN,
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_TEMPERATURE,
    COPILOT_HEADERS,
    COPILOT_TOKEN_URL,
    DEFAULT_CONTINUE_CONVERSATION,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_PROMPT,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    GITHUB_DEVICE_CODE_URL,
    GITHUB_DEVICE_LOGIN_URL,
    GITHUB_OAUTH_CLIENT_ID,
    GITHUB_OAUTH_TOKEN_URL,
)
from .utils import async_fetch_models

_LOGGER = logging.getLogger(__name__)


class CopilotConversationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow using GitHub Device Flow OAuth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._device_code: str | None = None
        self._user_code: str | None = None
        self._interval: int = 5
        self._access_token: str | None = None
        self._copilot_token: str | None = None
        self.login_task: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — redirect to device flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        return await self.async_step_device(user_input)

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the GitHub Device Flow OAuth."""

        if not self._device_code:
            # Step 1: Request a device code from GitHub
            session = async_get_clientsession(self.hass)
            try:
                async with session.post(
                    GITHUB_DEVICE_CODE_URL,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": GITHUB_OAUTH_CLIENT_ID,
                        "scope": "read:user",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        _LOGGER.error(
                            "GitHub device code request failed (%s): %s",
                            resp.status,
                            body,
                        )
                        return self.async_abort(reason="could_not_register")
                    data = await resp.json()
            except aiohttp.ClientError as err:
                _LOGGER.error("GitHub device code request error: %s", err)
                return self.async_abort(reason="could_not_register")

            self._device_code = data["device_code"]
            self._user_code = data["user_code"]
            self._interval = data.get("interval", 5)

        if self.login_task is None:
            self.login_task = self.hass.async_create_task(self._async_wait_for_auth())

        if self.login_task.done():
            if self.login_task.exception():
                _LOGGER.error("GitHub OAuth failed: %s", self.login_task.exception())
                return self.async_show_progress_done(next_step_id="could_not_register")
            return self.async_show_progress_done(next_step_id="choose_model")

        return self.async_show_progress(
            step_id="device",
            progress_action="wait_for_device",
            description_placeholders={
                "url": GITHUB_DEVICE_LOGIN_URL,
                "code": self._user_code or "",
            },
            progress_task=self.login_task,
        )

    async def _async_wait_for_auth(self) -> None:
        """Poll GitHub for device flow authorization."""
        session = async_get_clientsession(self.hass)

        while True:
            await asyncio.sleep(self._interval)

            try:
                async with session.post(
                    GITHUB_OAUTH_TOKEN_URL,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": GITHUB_OAUTH_CLIENT_ID,
                        "device_code": self._device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()
            except aiohttp.ClientError as err:
                _LOGGER.debug("OAuth poll error (will retry): %s", err)
                continue

            if "access_token" in data:
                self._access_token = data["access_token"]
                _LOGGER.debug("GitHub OAuth authorization successful")

                # Verify Copilot subscription by exchanging for Copilot token
                try:
                    async with session.get(
                        COPILOT_TOKEN_URL,
                        headers={
                            "Authorization": f"token {self._access_token}",
                            "Accept": "application/json",
                            **COPILOT_HEADERS,
                        },
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as token_resp:
                        if token_resp.status != 200:
                            body = await token_resp.text()
                            _LOGGER.error(
                                "Copilot token exchange failed (%s): %s",
                                token_resp.status,
                                body,
                            )
                            raise ValueError(
                                f"No Copilot subscription ({token_resp.status})"
                            )
                        token_data = await token_resp.json()
                        if not token_data.get("token"):
                            raise ValueError("Empty Copilot token")
                        self._copilot_token = token_data["token"]
                except aiohttp.ClientError as err:
                    raise ValueError(f"Copilot token exchange error: {err}") from err

                return

            error = data.get("error")
            if error == "authorization_pending":
                continue
            if error == "slow_down":
                self._interval += 5
                continue

            # Any other error is fatal
            raise ValueError(f"GitHub OAuth error: {data}")

    async def _async_fetch_models(self) -> list[str]:
        """Fetch available chat models using the copilot token from auth."""
        if not self._copilot_token:
            raise ValueError("Copilot token not available for fetching models")

        session = async_get_clientsession(self.hass)
        headers = {
            "Authorization": f"Bearer {self._copilot_token}",
            "Accept": "application/json",
            **COPILOT_HEADERS,
        }
        return await async_fetch_models(session, headers)

    async def async_step_choose_model(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user choose a model after successful auth."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="GitHub Copilot Conversation",
                data={CONF_GITHUB_TOKEN: self._access_token},
                options={CONF_MODEL: user_input[CONF_MODEL]},
            )

        model_list = await self._async_fetch_models()

        return self.async_show_form(
            step_id="choose_model",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MODEL,
                        default=DEFAULT_MODEL,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=model_list,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                }
            ),
        )

    async def async_step_could_not_register(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle auth failure — needs this step for progress_done transition."""
        return self.async_abort(reason="could_not_register")

    # ------------------------------------------------------------------
    # Reauth flow — same device flow pattern
    # ------------------------------------------------------------------
    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Handle reauth when token becomes invalid."""
        self._device_code = None
        self._user_code = None
        self._access_token = None
        self.login_task = None
        return await self.async_step_reauth_device()

    async def async_step_reauth_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reauth device flow — mirrors async_step_device."""
        if not self._device_code:
            session = async_get_clientsession(self.hass)
            try:
                async with session.post(
                    GITHUB_DEVICE_CODE_URL,
                    headers={"Accept": "application/json"},
                    data={
                        "client_id": GITHUB_OAUTH_CLIENT_ID,
                        "scope": "read:user",
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return self.async_abort(reason="could_not_register")
                    data = await resp.json()
            except aiohttp.ClientError:
                return self.async_abort(reason="could_not_register")

            self._device_code = data["device_code"]
            self._user_code = data["user_code"]
            self._interval = data.get("interval", 5)

        if self.login_task is None:
            self.login_task = self.hass.async_create_task(self._async_wait_for_auth())

        if self.login_task.done():
            if self.login_task.exception():
                return self.async_show_progress_done(next_step_id="could_not_register")
            return self.async_show_progress_done(next_step_id="reauth_finish")

        return self.async_show_progress(
            step_id="reauth_device",
            progress_action="wait_for_device",
            description_placeholders={
                "url": GITHUB_DEVICE_LOGIN_URL,
                "code": self._user_code or "",
            },
            progress_task=self.login_task,
        )

    async def async_step_reauth_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Finish reauth by updating the config entry."""
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={CONF_GITHUB_TOKEN: self._access_token},
        )

    # ------------------------------------------------------------------
    # Options flow
    # ------------------------------------------------------------------
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "CopilotOptionsFlow":
        return CopilotOptionsFlow()


class CopilotOptionsFlow(config_entries.OptionsFlow):
    """Options flow — HA injects self.config_entry as a read-only property."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            # Clean up empty LLM API selection
            if not user_input.get(CONF_LLM_HASS_API):
                user_input.pop(CONF_LLM_HASS_API, None)
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options

        # Fetch available models from the Copilot API
        runtime = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        model_list = await runtime.async_get_available_models()

        # Build LLM API options list
        hass_apis = [
            selector.SelectOptionDict(label=api.name, value=api.id)
            for api in llm.async_get_apis(self.hass)
        ]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    # ── Model ─────────────────────────────────────────────
                    vol.Optional(
                        CONF_MODEL,
                        default=opts.get(CONF_MODEL, DEFAULT_MODEL),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=model_list,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )
                    ),
                    # ── System prompt ─────────────────────────────────────
                    vol.Optional(
                        CONF_PROMPT,
                        default=opts.get(CONF_PROMPT, DEFAULT_PROMPT),
                    ): selector.TemplateSelector(),
                    # ── LLM API (Home Assistant device control) ───────────
                    vol.Optional(
                        CONF_LLM_HASS_API,
                        description={
                            "suggested_value": opts.get(CONF_LLM_HASS_API),
                        },
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=hass_apis,
                            multiple=True,
                        )
                    ),
                    # ── Temperature ───────────────────────────────────────
                    vol.Optional(
                        CONF_TEMPERATURE,
                        default=opts.get(CONF_TEMPERATURE, DEFAULT_TEMPERATURE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.0,
                            max=2.0,
                            step=0.05,
                            mode=selector.NumberSelectorMode.SLIDER,
                        )
                    ),
                    # ── Max tokens ────────────────────────────────────────
                    vol.Optional(
                        CONF_MAX_TOKENS,
                        default=opts.get(CONF_MAX_TOKENS, DEFAULT_MAX_TOKENS),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=64,
                            max=16384,
                            step=64,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    # ── Continue conversation (experimental) ──────────────
                    vol.Optional(
                        CONF_CONTINUE_CONVERSATION,
                        default=opts.get(
                            CONF_CONTINUE_CONVERSATION, DEFAULT_CONTINUE_CONVERSATION
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )
