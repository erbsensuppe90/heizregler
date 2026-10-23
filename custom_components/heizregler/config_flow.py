"""Config- und Options-Flow (Dropdowns für Sensor, Schalter, Leistung)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_LEISTUNG,
    CONF_LEISTUNG_AUTO,
    CONF_SENSOR,
    CONF_SENSOR_TIMEOUT,
    CONF_SWITCH,
    DEFAULT_SENSOR_TIMEOUT,
    DOMAIN,
    MAX_SCHALTER,
)
from .controller import entry_config, ist_leistungssensor, leistung_vorschlag, schalter_liste


def _regler_schema() -> dict:
    return {
        vol.Required(CONF_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="sensor", device_class="temperature")
        ),
        vol.Required(CONF_SWITCH): EntitySelector(
            EntitySelectorConfig(domain=["switch", "input_boolean"], multiple=True)
        ),
        vol.Required(CONF_SENSOR_TIMEOUT, default=DEFAULT_SENSOR_TIMEOUT): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=1440,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement="min",
            )
        ),
    }


def _leistung_schema() -> dict:
    # Kein device_class-Filter: auch Sensoren ohne Geräteklasse, aber mit W/kW,
    # sollen wählbar sein. Geprüft wird beim Speichern.
    return {
        vol.Optional(CONF_LEISTUNG): EntitySelector(
            EntitySelectorConfig(domain="sensor", multiple=True)
        ),
        vol.Required(CONF_LEISTUNG_AUTO, default=True): BooleanSelector(),
    }


def _schalter_belegt(
    entries: list[ConfigEntry], schalter: list[str], ausser: str | None = None
) -> bool:
    gewaehlt = set(schalter)
    return any(
        e.entry_id != ausser
        and gewaehlt & set(schalter_liste(entry_config(e).get(CONF_SWITCH)))
        for e in entries
    )


def _pruefen(
    entries: list[ConfigEntry], user_input: dict[str, Any], ausser: str | None = None
) -> dict[str, str]:
    schalter = schalter_liste(user_input.get(CONF_SWITCH))
    if not schalter:
        return {CONF_SWITCH: "kein_schalter"}
    if len(schalter) > MAX_SCHALTER:
        return {CONF_SWITCH: "zu_viele_schalter"}
    if _schalter_belegt(entries, schalter, ausser):
        return {CONF_SWITCH: "schalter_belegt"}
    return {}


def _leistung_pruefen(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    leistung = schalter_liste(user_input.get(CONF_LEISTUNG))
    if len(leistung) > MAX_SCHALTER:
        return {CONF_LEISTUNG: "zu_viele_leistung"}
    if any(not ist_leistungssensor(hass, eid) for eid in leistung):
        return {CONF_LEISTUNG: "kein_leistungssensor"}
    return {}


def _leistung_optionen(user_input: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_LEISTUNG: schalter_liste(user_input.get(CONF_LEISTUNG)),
        CONF_LEISTUNG_AUTO: bool(user_input.get(CONF_LEISTUNG_AUTO, True)),
    }


class HeizreglerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Neuen Regler anlegen."""

    VERSION = 3

    _daten: dict[str, Any]
    _vorschlag: list[str]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _pruefen(self._async_current_entries(), user_input)
            if not errors:
                self._daten = user_input
                self._vorschlag = leistung_vorschlag(
                    self.hass, schalter_liste(user_input[CONF_SWITCH])
                )
                if self._vorschlag:
                    return await self.async_step_leistung()
                # Kein Leistungssensor am Plug: Automatik bleibt an und greift,
                # falls später einer am Plug-Gerät auftaucht.
                return self._anlegen({CONF_LEISTUNG: [], CONF_LEISTUNG_AUTO: True})

        schema = vol.Schema({vol.Required(CONF_NAME): TextSelector(), **_regler_schema()})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_leistung(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional: Leistungssensoren der Plugs übernehmen."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _leistung_pruefen(self.hass, user_input)
            if not errors:
                return self._anlegen(_leistung_optionen(user_input))
        return self.async_show_form(
            step_id="leistung",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(_leistung_schema()),
                user_input or {CONF_LEISTUNG: self._vorschlag, CONF_LEISTUNG_AUTO: True},
            ),
            errors=errors,
        )

    def _anlegen(self, leistung: dict[str, Any]) -> ConfigFlowResult:
        d = self._daten
        return self.async_create_entry(
            title=d[CONF_NAME],
            data={
                CONF_SENSOR: d[CONF_SENSOR],
                CONF_SWITCH: schalter_liste(d[CONF_SWITCH]),
            },
            options={
                CONF_SENSOR_TIMEOUT: int(d[CONF_SENSOR_TIMEOUT]),
                **leistung,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HeizreglerOptionsFlow()


class HeizreglerOptionsFlow(OptionsFlow):
    """Sensor/Schalter/Timeout/Leistung nachträglich ändern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _pruefen(
                self.hass.config_entries.async_entries(DOMAIN),
                user_input,
                ausser=self.config_entry.entry_id,
            ) or _leistung_pruefen(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_SENSOR: user_input[CONF_SENSOR],
                        CONF_SWITCH: schalter_liste(user_input[CONF_SWITCH]),
                        CONF_SENSOR_TIMEOUT: int(user_input[CONF_SENSOR_TIMEOUT]),
                        **_leistung_optionen(user_input),
                    }
                )

        cfg = entry_config(self.config_entry)
        vorschlag = {
            **cfg,
            CONF_SWITCH: schalter_liste(cfg[CONF_SWITCH]),
            CONF_LEISTUNG: schalter_liste(cfg.get(CONF_LEISTUNG)),
            CONF_LEISTUNG_AUTO: cfg.get(CONF_LEISTUNG_AUTO, True),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({**_regler_schema(), **_leistung_schema()}),
                user_input or vorschlag,
            ),
            errors=errors,
        )
