"""Regel-Logik des Heizreglers (läuft im HA-Backend, unabhängig vom Dashboard)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
    split_entity_id,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from .const import (
    CONF_LEISTUNG,
    CONF_SENSOR,
    CONF_SENSOR_TIMEOUT,
    CONF_SWITCH,
    DEFAULT_HYSTERESE,
    DEFAULT_SENSOR_TIMEOUT,
    DEFAULT_SOLL,
    PRUEF_INTERVALL,
    Phase,
    Status,
)

_LOGGER = logging.getLogger(__name__)

_UNGUELTIG = (STATE_UNAVAILABLE, STATE_UNKNOWN)


def entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Daten + Optionen zusammenführen (Optionen gewinnen)."""
    return {**entry.data, **entry.options}


def schalter_liste(wert: str | list[str] | None) -> list[str]:
    """Schalter-Konfiguration immer als Liste (alte Einträge: einzelner String)."""
    if not wert:
        return []
    if isinstance(wert, str):
        return [wert]
    return list(dict.fromkeys(wert))


async def async_schalter_aus(hass: HomeAssistant, entity_ids: list[str]) -> None:
    """Schalter ausschalten, Fehler nur loggen."""
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None or state.state in _UNGUELTIG or state.state != STATE_ON:
            continue
        try:
            await hass.services.async_call(
                split_entity_id(entity_id)[0],
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Konnte %s nicht ausschalten: %s", entity_id, err)


class HeizreglerController:
    """Hysterese-Regler: EIN unter Soll, AUS über Soll + Hysterese."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        cfg = entry_config(entry)
        self.sensor_id: str = cfg[CONF_SENSOR]
        self.switch_ids: list[str] = schalter_liste(cfg[CONF_SWITCH])
        self.sensor_timeout: int = int(
            cfg.get(CONF_SENSOR_TIMEOUT, DEFAULT_SENSOR_TIMEOUT)
        )
        self.leistung_ids: list[str] = schalter_liste(cfg.get(CONF_LEISTUNG))

        # Werte werden von den Entities beim Start wiederhergestellt
        self.soll: float = DEFAULT_SOLL
        self.hysterese: float = DEFAULT_HYSTERESE
        self.aktiv: bool = False

        self.ist: float | None = None
        self.status: Status = Status.START
        self.phase: Phase | None = None
        self.fehler: str | None = None
        self.letzte_aktion: str | None = None
        self.letzte_schaltung: datetime | None = None

        self._started = False
        self._lock = asyncio.Lock()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._listeners: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------
    # Lebenszyklus
    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        """Listener registrieren. Erste Auswertung erst nach HA-Start."""
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.sensor_id, *self.switch_ids], self._handle_state_change
            )
        )
        if self.leistung_ids:
            # Leistung nur anzeigen, nie regeln -> nur Entities aktualisieren
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, self.leistung_ids, self._handle_leistung_change
                )
            )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._handle_interval, PRUEF_INTERVALL)
        )
        self._unsubs.append(async_at_started(self.hass, self._handle_started))

    @callback
    def async_stop(self) -> None:
        """Listener entfernen."""
        self._started = False
        while self._unsubs:
            self._unsubs.pop()()

    async def _handle_started(self, _hass: HomeAssistant) -> None:
        self._started = True
        await self.async_evaluate()

    async def _handle_interval(self, _now: datetime) -> None:
        await self.async_evaluate()

    @callback
    def _handle_state_change(self, _event: Event[EventStateChangedData]) -> None:
        if self._started:
            self.entry.async_create_task(self.hass, self.async_evaluate())

    # ------------------------------------------------------------------
    # Entity-Anbindung
    # ------------------------------------------------------------------
    @callback
    def async_add_listener(self, cb: CALLBACK_TYPE) -> CALLBACK_TYPE:
        """Entity über Änderungen informieren lassen."""
        self._listeners.append(cb)

        @callback
        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    @property
    def aus_ab(self) -> float:
        """Ausschaltgrenze."""
        return round(self.soll + self.hysterese, 2)

    async def async_set_soll(self, wert: float) -> None:
        self.soll = float(wert)
        self._notify()
        await self.async_evaluate()

    async def async_set_hysterese(self, wert: float) -> None:
        self.hysterese = float(wert)
        self._notify()
        await self.async_evaluate()

    async def async_set_aktiv(self, aktiv: bool) -> None:
        war_aktiv = self.aktiv
        self.aktiv = aktiv
        self._notify()
        if war_aktiv and not aktiv and self._started:
            async with self._lock:
                await self._schalten(self._schalter_pruefen()[0], False, "Regelung deaktiviert")
        await self.async_evaluate()

    # ------------------------------------------------------------------
    # Regel-Logik
    # ------------------------------------------------------------------
    async def async_evaluate(self) -> None:
        """Zustand prüfen und ggf. schalten."""
        if not self._started:
            return
        async with self._lock:
            await self._evaluate()
        self._notify()

    def _schalter_pruefen(self) -> tuple[list[str], list[str]]:
        """(erreichbare Schalter, Fehlertexte für nicht erreichbare)."""
        ok: list[str] = []
        fehler: list[str] = []
        for eid in self.switch_ids:
            st = self.hass.states.get(eid)
            if st is None:
                fehler.append(f"{eid} existiert nicht")
            elif st.state in _UNGUELTIG:
                fehler.append(f"{eid} ist {st.state}")
            else:
                ok.append(eid)
        return ok, fehler

    @callback
    def _handle_leistung_change(self, _event: Event[EventStateChangedData]) -> None:
        self._notify()

    @property
    def leistung(self) -> float | None:
        """Summe der Leistungssensoren in W. None = keiner konfiguriert/gültig."""
        summe = 0.0
        gueltig = False
        for eid in self.leistung_ids:
            wert = _leistung_w(self.hass.states.get(eid))
            if wert is not None:
                summe += wert
                gueltig = True
        return round(summe, 1) if gueltig else None

    @property
    def schalter_an(self) -> int:
        """Anzahl eingeschalteter Schalter."""
        return sum(
            1
            for eid in self.switch_ids
            if (st := self.hass.states.get(eid)) is not None and st.state == STATE_ON
        )

    async def _evaluate(self) -> None:
        sensor = self.hass.states.get(self.sensor_id)

        self.ist = _temperatur(sensor)
        self.phase = self._phase()
        self.fehler = None

        if not self.aktiv:
            self.status = Status.INAKTIV
            return

        erreichbar, schalter_fehler = self._schalter_pruefen()
        meldungen: list[str] = list(schalter_fehler)

        if not erreichbar:
            self.fehler = "; ".join(meldungen) or "kein Schalter konfiguriert"
            self.status = Status.SCHALTERFEHLER
            return

        sensor_fehler = self._sensor_fehler(sensor)
        if sensor_fehler:
            # Fail-safe: ohne gültigen Messwert nicht heizen
            ok = await self._schalten(erreichbar, False, "Sensorfehler")
            self.fehler = "; ".join([sensor_fehler, *meldungen])
            self.status = Status.SENSORFEHLER if ok else Status.SCHALTERFEHLER
            return

        ok = True
        if self.phase is Phase.UNTER_SOLL:
            ok = await self._schalten(erreichbar, True, f"Ist {self.ist} < Soll {self.soll}")
        elif self.phase is Phase.UEBER_GRENZE:
            ok = await self._schalten(erreichbar, False, f"Ist {self.ist} > {self.aus_ab}")
        # Phase.BAND: Zustand halten

        self.fehler = "; ".join(meldungen) or None
        if not ok:
            self.status = Status.SCHALTERFEHLER
            return
        self.status = Status.HEIZEN if self.schalter_an > 0 else Status.AUS

    def _phase(self) -> Phase | None:
        if self.ist is None:
            return None
        if self.ist < self.soll:
            return Phase.UNTER_SOLL
        if self.ist > self.aus_ab:
            return Phase.UEBER_GRENZE
        return Phase.BAND

    def _sensor_fehler(self, sensor: State | None) -> str | None:
        """Grund, warum der Sensorwert nicht nutzbar ist (None = ok)."""
        if sensor is None:
            return f"{self.sensor_id} existiert nicht"
        if self.ist is None:
            return f"{self.sensor_id} hat keinen Zahlenwert: '{sensor.state}'"
        if self.sensor_timeout > 0:
            alter = dt_util.utcnow() - sensor.last_reported
            if alter > timedelta(minutes=self.sensor_timeout):
                return (
                    f"letzter Sensorwert vor {int(alter.total_seconds() // 60)} min "
                    f"(Timeout {self.sensor_timeout} min)"
                )
        return None

    async def _schalten(self, entity_ids: list[str], ein: bool, grund: str) -> bool:
        """Erreichbare Schalter gemeinsam setzen. True = alle ok."""
        zu_schalten = [
            eid
            for eid in entity_ids
            if (st := self.hass.states.get(eid)) is not None and (st.state == STATE_ON) != ein
        ]
        if not zu_schalten:
            return True
        alles_ok = True
        for eid in zu_schalten:
            try:
                await self.hass.services.async_call(
                    split_entity_id(eid)[0],
                    SERVICE_TURN_ON if ein else SERVICE_TURN_OFF,
                    {ATTR_ENTITY_ID: eid},
                    blocking=True,
                )
            except HomeAssistantError as err:
                _LOGGER.warning(
                    "%s: Schalten von %s fehlgeschlagen: %s", self.entry.title, eid, err
                )
                alles_ok = False
        self.letzte_aktion = f"{'EIN' if ein else 'AUS'}: {grund}"
        self.letzte_schaltung = dt_util.utcnow()
        _LOGGER.info(
            "%s: %s -> %s", self.entry.title, ", ".join(zu_schalten), self.letzte_aktion
        )
        return alles_ok


def _temperatur(state: State | None) -> float | None:
    if state is None or state.state in _UNGUELTIG:
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


_FAKTOR_W = {"W": 1.0, "kW": 1000.0, "MW": 1_000_000.0, "mW": 0.001}


def _leistung_w(state: State | None) -> float | None:
    """Leistung eines Sensors in Watt (W/kW/MW/mW), sonst None."""
    if state is None or state.state in _UNGUELTIG:
        return None
    try:
        wert = float(state.state)
    except (TypeError, ValueError):
        return None
    faktor = _FAKTOR_W.get(state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) or "W")
    if faktor is None:
        return None
    return wert * faktor
