"""Thermostat-Entity: Ist, Soll, Regelung (heat/off), Plug-Zustand (hvac_action)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeizreglerConfigEntry
from .const import SOLL_MAX, SOLL_MIN, SOLL_STEP
from .entity import HeizreglerEntity

KEY_CLIMATE = "climate"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizreglerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HeizreglerClimate(entry.runtime_data, KEY_CLIMATE, None)])


class HeizreglerClimate(HeizreglerEntity, ClimateEntity):
    """Thermostat-Sicht auf den Regler. Werte liegen im Controller."""

    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = SOLL_STEP
    _attr_min_temp = SOLL_MIN
    _attr_max_temp = SOLL_MAX
    _attr_precision = 0.1

    @property
    def current_temperature(self) -> float | None:
        return self.controller.ist

    @property
    def target_temperature(self) -> float:
        return self.controller.soll

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self.controller.aktiv else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        if not self.controller.aktiv:
            return HVACAction.OFF
        return HVACAction.HEATING if self.controller.schalter_an > 0 else HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.controller
        return {"hysterese": c.hysterese, "aus_ueber": c.aus_ab, "status": c.status.value}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(mode)
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.controller.async_set_soll(min(max(float(temp), SOLL_MIN), SOLL_MAX))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.controller.async_set_aktiv(hvac_mode == HVACMode.HEAT)

    async def async_turn_on(self) -> None:
        await self.controller.async_set_aktiv(True)

    async def async_turn_off(self) -> None:
        await self.controller.async_set_aktiv(False)
