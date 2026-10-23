"""Status-Sensor (Grundlage für die Karte)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HeizreglerConfigEntry
from .const import (
    DOMAIN,
    KEY_HYSTERESE,
    KEY_LEISTUNG,
    KEY_REGELUNG,
    KEY_SOLL,
    KEY_STATUS,
    Status,
)
from .entity import HeizreglerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeizreglerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    c = entry.runtime_data
    entities: list[SensorEntity] = [HeizreglerStatusSensor(c, KEY_STATUS, "Status")]
    if c.leistung_ids:
        entities.append(HeizreglerLeistungSensor(c, KEY_LEISTUNG, "Leistung"))
    async_add_entities(entities)


class HeizreglerStatusSensor(HeizreglerEntity, SensorEntity):
    """Status + alle Werte als Attribute."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [s.value for s in Status]
    _attr_translation_key = "status"
    _attr_icon = "mdi:radiator"
    _unrecorded_attributes = frozenset(
        {
            "temperatur_sensor",
            "schalter",
            "soll_entity",
            "hysterese_entity",
            "regelung_entity",
            "climate_entity",
            "leistung_sensoren",
        }
    )

    @property
    def native_value(self) -> str:
        return self.controller.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.controller
        reg = er.async_get(self.hass)
        eid = c.entry.entry_id

        def _id(domain: str, key: str) -> str | None:
            return reg.async_get_entity_id(domain, DOMAIN, f"{eid}_{key}")

        return {
            "ist_temperatur": c.ist,
            "soll": c.soll,
            "hysterese": c.hysterese,
            "ein_unter": c.soll,
            "aus_ueber": c.aus_ab,
            "phase": c.phase.value if c.phase else None,
            "fehler": c.fehler,
            "letzte_aktion": c.letzte_aktion,
            "letzte_schaltung": c.letzte_schaltung.isoformat() if c.letzte_schaltung else None,
            "temperatur_sensor": c.sensor_id,
            "schalter": c.switch_ids,
            "schalter_an": c.schalter_an,
            "soll_entity": _id("number", KEY_SOLL),
            "hysterese_entity": _id("number", KEY_HYSTERESE),
            "regelung_entity": _id("switch", KEY_REGELUNG),
            "climate_entity": _id("climate", "climate"),
            "leistung": c.leistung,
            "leistung_sensoren": c.leistung_ids,
            "leistung_automatisch": c.leistung_automatisch,
        }


class HeizreglerLeistungSensor(HeizreglerEntity, SensorEntity):
    """Summe der gewählten Leistungssensoren (nur Anzeige)."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:flash"

    @property
    def available(self) -> bool:
        return self.controller.leistung is not None

    @property
    def native_value(self) -> float | None:
        return self.controller.leistung
