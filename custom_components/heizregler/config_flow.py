"""Config- und Options-Flow (Dropdowns für Sensor und Schalter)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_SENSOR,
    CONF_SENSOR_TIMEOUT,
    CONF_SWITCH,
    DEFAULT_SENSOR_TIMEOUT,
    DOMAIN,
    MAX_SCHALTER,
)
from .controller import entry_config, schalter_liste


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


class HeizreglerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Neuen Regler anlegen."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _pruefen(self._async_current_entries(), user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_SENSOR: user_input[CONF_SENSOR],
                        CONF_SWITCH: schalter_liste(user_input[CONF_SWITCH]),
                    },
                    options={
                        CONF_SENSOR_TIMEOUT: int(user_input[CONF_SENSOR_TIMEOUT]),
                    },
                )

        schema = vol.Schema({vol.Required(CONF_NAME): TextSelector(), **_regler_schema()})
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HeizreglerOptionsFlow()


class HeizreglerOptionsFlow(OptionsFlow):
    """Sensor/Schalter/Timeout nachträglich ändern."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _pruefen(
                self.hass.config_entries.async_entries(DOMAIN),
                user_input,
                ausser=self.config_entry.entry_id,
            )
            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_SENSOR: user_input[CONF_SENSOR],
                        CONF_SWITCH: schalter_liste(user_input[CONF_SWITCH]),
                        CONF_SENSOR_TIMEOUT: int(user_input[CONF_SENSOR_TIMEOUT]),
                    }
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(_regler_schema()),
                user_input
                or {
                    **entry_config(self.config_entry),
                    CONF_SWITCH: schalter_liste(entry_config(self.config_entry)[CONF_SWITCH]),
                },
            ),
            errors=errors,
        )
