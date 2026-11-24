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
from homeassistant.const import CONF_HOST, CONF_PORT, UnitOfTime
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .api import (
    FroniusConnectionError,
    FroniusModbusError,
    InverterInfo,
    async_detect_meter,
)
from .client_pool import async_acquire_client, async_release_client
from .const import (
    CONF_ALLOW_CONTROL,
    CONF_EXTRA_METER_UNIT_IDS,
    CONF_METER_UNIT_ID,
    CONF_SCAN_INTERVAL,
    CONF_SITE_REGISTERS,
    CONF_UNIT_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MANUFACTURER,
    MAX_SCAN_INTERVAL_SECONDS,
    METER_UNIT_ID_CANDIDATES,
    METER_UNIT_ID_NONE,
    MIN_SCAN_INTERVAL_SECONDS,
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
        # weitere Zähler, durch Komma getrennt (z. B. "201, 202")
        vol.Optional(CONF_EXTRA_METER_UNIT_IDS): str,
    }
)


def parse_unit_ids(text: str | None, exclude: set[int | None]) -> list[int]:
    """Kommagetrennte Unit-IDs (1–247) lesen; doppelte und ausgeschlossene entfallen.

    ValueError bei allem, was keine gültige Unit-ID ist.
    """
    units: list[int] = []
    for part in (text or "").replace(";", ",").split(","):
        if not (part := part.strip()):
            continue
        unit = int(part)
        if not 1 <= unit <= 247:
            raise ValueError(f"Unit-ID {unit} außerhalb 1–247")
        if unit not in exclude and unit not in units:
            units.append(unit)
    return units


class FroniusModbusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung über die Benutzeroberfläche."""

    VERSION = 1

    # per DHCP gefundene Adresse, als Vorschlag im Einrichtungsformular
    _discovered_host: str | None = None

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

        extra_units: list[int] = []
        if not errors:
            try:
                extra_units = parse_unit_ids(
                    user_input.get(CONF_EXTRA_METER_UNIT_IDS), exclude={unit, meter_unit}
                )
            except ValueError:
                errors[CONF_EXTRA_METER_UNIT_IDS] = "invalid_meter_list"
            for extra in extra_units:
                if await async_detect_meter(host, port, [extra]) is None:
                    _LOGGER.warning(
                        "Einrichtung %s:%s: kein Smart Meter unter Unit-ID %s "
                        "(GEN24: 200–204, Datamanager: 240–244)",
                        host, port, extra,
                    )
                    errors[CONF_EXTRA_METER_UNIT_IDS] = "meter_not_found"
                    break

        data: dict[str, Any] = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_UNIT_ID: unit,
            CONF_METER_UNIT_ID: meter_unit,
            CONF_EXTRA_METER_UNIT_IDS: extra_units,
        }
        if info is not None and info.site_registers_confirmed:
            # Gerätetyp (Datamanager / GEN24) dauerhaft merken
            data[CONF_SITE_REGISTERS] = info.has_site_registers
        return info, data, errors

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Fronius-Gerät im Netzwerk gesehen (DHCP, MAC-Präfix 00:03:AC).

        Antwortet es per Modbus TCP unter den Standardwerten (Port 502, Adresse 1),
        wird es zur Einrichtung vorgeschlagen. Ist das Gerät schon eingerichtet,
        aber unter einer anderen IP-Adresse, wird diese aktualisiert. Ohne Modbus-
        Antwort (Modbus TCP aus, anderer Port, andere Adresse) passiert nichts.
        """
        host = discovery_info.ip
        entries = self._async_current_entries(include_ignore=False)
        if any(entry.data.get(CONF_HOST) == host for entry in entries):
            return self.async_abort(reason="already_configured")

        client = async_acquire_client(self.hass, host, DEFAULT_PORT)
        try:
            info = await client.read_inverter_info(DEFAULT_UNIT_ID)
        except FroniusModbusError as err:
            _LOGGER.debug("DHCP-Erkennung %s: kein Modbus-Gerät (%s)", host, err)
            return self.async_abort(reason="cannot_connect")
        finally:
            await async_release_client(self.hass, host, DEFAULT_PORT)

        await self.async_set_unique_id(info.serial_number or None)
        known = next((e for e in entries if e.unique_id == self.unique_id), None)
        if known is not None and self.unique_id:
            # Neue IP-Adresse: alle Einträge am bisherigen Host umziehen (mehrere
            # Wechselrichter an einem Datamanager teilen sich die Adresse)
            old_host = known.data.get(CONF_HOST)
            for entry in entries:
                if entry.data.get(CONF_HOST) == old_host:
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_HOST: host}
                    )
                    self.hass.config_entries.async_schedule_reload(entry.entry_id)
            _LOGGER.info(
                "%s hat eine neue IP-Adresse: %s statt %s", info.model, host, old_host
            )
            return self.async_abort(reason="already_configured")

        self._discovered_host = host
        self.context["title_placeholders"] = {
            "name": f"{info.model or MANUFACTURER} ({host})"
        }
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            info, data, errors = await self._async_validate(user_input)
            if info is not None and not errors:
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
                STEP_USER_DATA_SCHEMA,
                user_input
                or ({CONF_HOST: self._discovered_host} if self._discovered_host else None),
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
            if info is not None and not errors:
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
            CONF_EXTRA_METER_UNIT_IDS: ", ".join(
                str(u) for u in entry.data.get(CONF_EXTRA_METER_UNIT_IDS, [])
            ),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, suggested
            ),
            errors=errors,
        )


class FroniusOptionsFlow(OptionsFlow):
    """Optionen: Steuerung erlauben (Standard: aus) und Abfrageintervall."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(data=user_input)
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ALLOW_CONTROL,
                        default=options.get(CONF_ALLOW_CONTROL, False),
                    ): bool,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
                        ),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                            step=1,
                            unit_of_measurement=UnitOfTime.SECONDS,
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
