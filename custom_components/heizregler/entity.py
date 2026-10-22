"""Gemeinsame Basis-Entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VERSION
from .controller import HeizreglerController


class HeizreglerEntity(Entity):
    """Basis: Gerät pro Regler, Updates vom Controller."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, controller: HeizreglerController, key: str, name: str) -> None:
        self.controller = controller
        entry = controller.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Heizregler",
            model="Hysterese-Regler",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.controller.async_add_listener(self.async_write_ha_state))
