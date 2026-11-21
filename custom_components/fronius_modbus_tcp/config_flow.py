"""Config Flow für Fronius Modbus TCP."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import (
    FroniusConnectionError,
    FroniusModbusClient,
    FroniusModbusError,
    async_detect_meter,
)
from .const import (
    CONF_METER_UNIT_ID,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    METER_UNIT_ID_CANDIDATES,
    METER_UNIT_ID_NONE,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=247)
        ),
        # leer = automatisch suchen, 0 = kein Smart Meter
        vol.Optional(CONF_METER_UNIT_ID): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=247)
        ),
    }
)


class FroniusModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung über die Benutzeroberfläche."""

    VERSION = 1

    def _host_has_meter(self, host: str) -> bool:
        """Smart Meter am selben Host schon einem anderen Eintrag zugeordnet?

        Mehrere Wechselrichter an einem Datamanager teilen sich einen Zähler –
        automatisch wird er nur dem ersten Eintrag zugeordnet.
        """
        return any(
            entry.data.get(CONF_HOST) == host and entry.data.get(CONF_METER_UNIT_ID)
            for entry in self._async_current_entries(include_ignore=False)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host, port = user_input[CONF_HOST], user_input[CONF_PORT]
            client = FroniusModbusClient(host, port)
            try:
                info = await client.read_inverter_info(user_input[CONF_UNIT_ID])
            except FroniusConnectionError:
                errors["base"] = "cannot_connect"
            except FroniusModbusError:
                errors["base"] = "not_sunspec"
            except Exception:
                _LOGGER.exception("Unerwarteter Fehler")
                errors["base"] = "unknown"
            finally:
                await client.close()

            meter_unit: int | None = None
            if not errors:
                requested = user_input.get(CONF_METER_UNIT_ID)
                if requested is None:
                    if not self._host_has_meter(host):
                        meter = await async_detect_meter(
                            host, port, METER_UNIT_ID_CANDIDATES
                        )
                        meter_unit = meter.unit_id if meter else None
                elif requested != METER_UNIT_ID_NONE:
                    if await async_detect_meter(host, port, [requested]) is None:
                        errors[CONF_METER_UNIT_ID] = "meter_not_found"
                    meter_unit = requested

            if not errors:
                await self.async_set_unique_id(info.serial_number or None)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{info.manufacturer} {info.model}".strip() or host,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_UNIT_ID: user_input[CONF_UNIT_ID],
                        CONF_METER_UNIT_ID: meter_unit,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )
