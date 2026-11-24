"""Config Flow für Fronius Modbus TCP."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_PORT

from .api import (
    FroniusConnectionError,
    FroniusModbusError,
    InverterInfo,
    async_detect_meter,
)
from .client_pool import async_acquire_client, async_release_client
from .const import (
    CONF_ALLOW_CONTROL,
    CONF_METER_UNIT_ID,
    CONF_SITE_REGISTERS,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> FroniusOptionsFlow:
        return FroniusOptionsFlow()

    def _host_has_meter(self, host: str, exclude_entry_id: str | None = None) -> bool:
        """Smart Meter am selben Host schon einem anderen Eintrag zugeordnet?

        Mehrere Wechselrichter an einem Datamanager teilen sich einen Zähler –
        automatisch wird er nur dem ersten Eintrag zugeordnet.
        """
        return any(
            entry.data.get(CONF_HOST) == host and entry.data.get(CONF_METER_UNIT_ID)
            for entry in self._async_current_entries(include_ignore=False)
            if entry.entry_id != exclude_entry_id
        )

    async def _async_validate(
        self, user_input: dict[str, Any], exclude_entry_id: str | None = None
    ) -> tuple[InverterInfo | None, dict[str, Any], dict[str, str]]:
        """Eingaben am Gerät prüfen: Wechselrichter erkennen, Smart Meter suchen.

        Rückgabe: (Wechselrichter, Daten für den Config-Eintrag, Fehler).
        """
        errors: dict[str, str] = {}
        host, port = user_input[CONF_HOST], user_input[CONF_PORT]
        unit = user_input[CONF_UNIT_ID]
        info: InverterInfo | None = None
        # Läuft am selben Gerät schon ein Eintrag, wird dessen Verbindung
        # mitbenutzt (Abfragen nacheinander, Vorgabe Fronius)
        client = async_acquire_client(self.hass, host, port)
        try:
            info = await client.read_inverter_info(unit)
        except FroniusConnectionError as err:
            _LOGGER.warning(
                "Einrichtung %s:%s (Unit-ID %s): keine Verbindung – %s. "
                "Modbus TCP am Gerät aktiv? Port korrekt?",
                host, port, unit, err,
            )
            errors["base"] = "cannot_connect"
        except FroniusModbusError as err:
            _LOGGER.warning(
                "Einrichtung %s:%s (Unit-ID %s): Gerät antwortet, aber keine "
                "SunSpec-Wechselrichterdaten – %s. GEN24/Tauro/Verto: Unit-ID 1; "
                "Datamanager: Wechselrichter-Nummer (00 → 100)",
                host, port, unit, err,
            )
            errors["base"] = "not_sunspec"
        except Exception:
            _LOGGER.exception(
                "Einrichtung %s:%s (Unit-ID %s): unerwarteter Fehler",
                host, port, unit,
            )
            errors["base"] = "unknown"
        else:
            _LOGGER.info(
                "Einrichtung %s:%s (Unit-ID %s): %s %s erkannt, Modelle %s",
                host, port, unit, info.manufacturer, info.model,
                sorted(info.models),
            )
        finally:
            await async_release_client(self.hass, host, port)

        meter_unit: int | None = None
        if not errors:
            requested = user_input.get(CONF_METER_UNIT_ID)
            if requested is None:
                if not self._host_has_meter(host, exclude_entry_id):
                    meter = await async_detect_meter(
                        host, port, METER_UNIT_ID_CANDIDATES
                    )
                    meter_unit = meter.unit_id if meter else None
                else:
                    _LOGGER.info(
                        "Einrichtung %s: Smart Meter bereits einem anderen "
                        "Eintrag zugeordnet, keine automatische Suche",
                        host,
                    )
            elif requested != METER_UNIT_ID_NONE:
                if await async_detect_meter(host, port, [requested]) is None:
                    _LOGGER.warning(
                        "Einrichtung %s:%s: kein Smart Meter unter Unit-ID %s "
                        "(GEN24: 200–204, Datamanager: 240–244)",
                        host, port, requested,
                    )
                    errors[CONF_METER_UNIT_ID] = "meter_not_found"
                meter_unit = requested

        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_UNIT_ID: unit,
            CONF_METER_UNIT_ID: meter_unit,
        }
        if info is not None and info.site_registers_confirmed:
            # Gerätetyp (Datamanager / GEN24) dauerhaft merken
            data[CONF_SITE_REGISTERS] = info.has_site_registers
        return info, data, errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            info, data, errors = await self._async_validate(user_input)
            if not errors:
                assert info is not None
                await self.async_set_unique_id(info.serial_number or None)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{info.manufacturer} {info.model}".strip()
                    or data[CONF_HOST],
                    data=data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verbindungsdaten eines bestehenden Eintrags ändern (z. B. neue IP-Adresse).

        Das Gerät muss dasselbe bleiben (Seriennummer); sonst gingen Entitäten
        und Historie auf ein anderes Gerät über.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            info, data, errors = await self._async_validate(user_input, entry.entry_id)
            if not errors:
                assert info is not None
                await self.async_set_unique_id(info.serial_number or None)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                if CONF_SITE_REGISTERS not in data and CONF_SITE_REGISTERS in entry.data:
                    # nicht eindeutig geprüft → bisheriges Ergebnis behalten
                    data[CONF_SITE_REGISTERS] = entry.data[CONF_SITE_REGISTERS]
                return self.async_update_reload_and_abort(entry, data=data)

        suggested = user_input or {
            **entry.data,
            # ohne Zähler eingerichtet → 0 vorschlagen, damit sich daran nichts
            # ändert; Feld leeren startet die automatische Suche
            CONF_METER_UNIT_ID: entry.data.get(CONF_METER_UNIT_ID)
            or METER_UNIT_ID_NONE,
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested
            ),
            errors=errors,
        )


class FroniusOptionsFlow(OptionsFlow):
    """Optionen: Steuerung des Wechselrichters erlauben (Standard: aus)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ALLOW_CONTROL,
                        default=self.config_entry.options.get(CONF_ALLOW_CONTROL, False),
                    ): bool,
                }
            ),
        )
