"""Konstanten für Heizregler."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "heizregler"
VERSION = "0.4.0"

CONF_SENSOR = "temperatur_sensor"
CONF_SWITCH = "schalter"
CONF_SENSOR_TIMEOUT = "sensor_timeout"

DEFAULT_SOLL = 21.0
DEFAULT_HYSTERESE = 0.5
DEFAULT_SENSOR_TIMEOUT = 0  # Minuten, 0 = aus
MAX_SCHALTER = 3

SOLL_MIN = 5.0
SOLL_MAX = 30.0
SOLL_STEP = 0.5
HYSTERESE_MIN = 0.1
HYSTERESE_MAX = 3.0
HYSTERESE_STEP = 0.1

# Zyklische Nachprüfung, falls ein Schaltbefehl verloren ging
PRUEF_INTERVALL = timedelta(seconds=60)

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CARD_URL = "/heizregler_static/heizregler-card.js"
PANEL_URL = "/heizregler_static/heizregler-panel.js"
PANEL_URL_PATH = "heizregler"
PANEL_TITLE = "Heizregler"
PANEL_ICON = "mdi:thermostat"

KEY_SOLL = "soll"
KEY_HYSTERESE = "hysterese"
KEY_REGELUNG = "regelung"
KEY_STATUS = "status"


class Status(StrEnum):
    """Status des Reglers."""

    START = "start"
    HEIZEN = "heizen"
    AUS = "aus"
    INAKTIV = "inaktiv"
    SENSORFEHLER = "sensorfehler"
    SCHALTERFEHLER = "schalterfehler"


class Phase(StrEnum):
    """Lage der Ist-Temperatur relativ zu den Schaltgrenzen."""

    UNTER_SOLL = "unter_soll"
    BAND = "band"
    UEBER_GRENZE = "ueber_grenze"
