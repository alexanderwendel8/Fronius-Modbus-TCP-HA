"""Config Flow für Fronius Modbus TCP."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import FroniusConnectionError, FroniusModbusClient, FroniusModbusError
from .const import CONF_UNIT_ID, DEFAULT_PORT, DEFAULT_UNIT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=247)
        ),
    }
)


class FroniusModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung über die Benutzeroberfläche."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = FroniusModbusClient(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_UNIT_ID]
            )
            try:
                info = await client.read_device_info()
            except FroniusConnectionError:
                errors["base"] = "cannot_connect"
            except FroniusModbusError:
                errors["base"] = "not_sunspec"
            except Exception:
                _LOGGER.exception("Unerwarteter Fehler")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.serial_number or None)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{info.manufacturer} {info.model}".strip()
                    or user_input[CONF_HOST],
                    data=user_input,
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
