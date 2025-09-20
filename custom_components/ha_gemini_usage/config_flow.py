"""Config flow for Google Gemini Usage integration."""
import logging
from typing import Any

import voluptuous as vol
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)

async def validate_api_key(api_key: str, hass) -> None:
    """Validate the API key by making a test call to the API."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-pro')
    # Use run_in_executor to avoid blocking the event loop
    await hass.async_add_executor_job(model.generate_content, "test")


class GeminiUsageConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Gemini Usage."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            try:
                await validate_api_key(api_key, self.hass)
                # Set a unique ID to prevent multiple entries for the same account
                await self.async_set_unique_id("gemini_usage_main_account")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Google Gemini Usage", data=user_input
                )
            except google_exceptions.PermissionDenied:
                errors["base"] = "invalid_auth"
            except google_exceptions.GoogleAPIError:
                errors["base"] = "cannot_connect"
            except Exception as e:
                _LOGGER.exception("Unexpected exception: %s", e)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
