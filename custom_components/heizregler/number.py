"""Soll und Hysterese als einstellbare Zahlen (werden über Neustart gemerkt)."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeizreglerConfigEntry
from .const import (
    HYSTERESE_MAX,
    HYSTERESE_MIN,
    HYSTERESE_STEP,
    KEY_HYSTERESE,
    KEY_SOLL,
    SOLL_MAX,
    SOLL_MIN,
    SOLL_STEP,
)
from .controller import HeizreglerController
from .entity import HeizreglerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizreglerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            HeizreglerNumber(c, KEY_SOLL, "Soll", SOLL_MIN, SOLL_MAX, SOLL_STEP, "mdi:thermometer"),
            HeizreglerNumber(
                c, KEY_HYSTERESE, "Hysterese", HYSTERESE_MIN, HYSTERESE_MAX, HYSTERESE_STEP, "mdi:arrow-expand-vertical"
            ),
        ]
    )


class HeizreglerNumber(HeizreglerEntity, RestoreNumber):
    """Einstellwert des Reglers."""

    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        controller: HeizreglerController,
        key: str,
        name: str,
        minimum: float,
        maximum: float,
        step: float,
        icon: str,
    ) -> None:
        super().__init__(controller, key, name)
        self._key = key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            wert = min(max(float(last.native_value), self.native_min_value), self.native_max_value)
            setattr(self.controller, self._key, wert)

    @property
    def native_value(self) -> float:
        return getattr(self.controller, self._key)

    async def async_set_native_value(self, value: float) -> None:
        if self._key == KEY_SOLL:
            await self.controller.async_set_soll(value)
        else:
            await self.controller.async_set_hysterese(value)
