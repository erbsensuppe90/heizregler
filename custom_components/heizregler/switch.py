"""Regelung an/aus (wird über Neustart gemerkt)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HeizreglerConfigEntry
from .const import KEY_REGELUNG
from .entity import HeizreglerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizreglerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([HeizreglerRegelungSwitch(entry.runtime_data, KEY_REGELUNG, "Regelung")])


class HeizreglerRegelungSwitch(HeizreglerEntity, SwitchEntity, RestoreEntity):
    """Schaltet die automatische Regelung ein/aus."""

    _attr_icon = "mdi:thermostat-auto"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self.controller.aktiv = last.state == STATE_ON

    @property
    def is_on(self) -> bool:
        return self.controller.aktiv

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_set_aktiv(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_set_aktiv(False)
