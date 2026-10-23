"""Tests für Heizregler: Config-Flow, Hysterese-Logik, Fail-safe."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from custom_components.heizregler.const import (
    CONF_SENSOR,
    CONF_SENSOR_TIMEOUT,
    CONF_SWITCH,
    DOMAIN,
)

SENSOR = "sensor.hobbykeller_temperature"
PLUG = "input_boolean.plug"
PLUG2 = "input_boolean.plug2"

SOLL = "number.hobbykeller_soll"
HYST = "number.hobbykeller_hysterese"
REGELUNG = "switch.hobbykeller_regelung"
STATUS = "sensor.hobbykeller_status"


async def _basis(hass: HomeAssistant) -> None:
    assert await async_setup_component(
        hass, "input_boolean", {"input_boolean": {"plug": {}, "plug2": {}, "plug3": {}, "plug4": {}}}
    )
    hass.states.async_set(SENSOR, "20.0", {"device_class": "temperature", "unit_of_measurement": "°C"})


async def _anlegen(hass: HomeAssistant, name="Hobbykeller", switch=PLUG):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": name, CONF_SENSOR: SENSOR, CONF_SWITCH: switch if isinstance(switch, list) else [switch], CONF_SENSOR_TIMEOUT: 0},
    )
    await hass.async_block_till_done()
    return result


async def _setze(hass, entity_id, wert):
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": wert}, blocking=True
    )
    await hass.async_block_till_done()


async def _regelung(hass, an: bool):
    await hass.services.async_call(
        "switch", "turn_on" if an else "turn_off", {"entity_id": REGELUNG}, blocking=True
    )
    await hass.async_block_till_done()


async def _temp(hass, wert):
    hass.states.async_set(SENSOR, wert, {"device_class": "temperature", "unit_of_measurement": "°C"})
    await hass.async_block_till_done()


def _plug(hass):
    return hass.states.get(PLUG).state


async def test_flow_und_entities(hass: HomeAssistant) -> None:
    await _basis(hass)
    result = await _anlegen(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hobbykeller"
    for eid in (SOLL, HYST, REGELUNG, STATUS):
        assert hass.states.get(eid) is not None, eid
    assert hass.states.get(SOLL).state == "21.0"
    assert hass.states.get(HYST).state == "0.5"
    assert hass.states.get(REGELUNG).state == STATE_OFF  # Standard: aus
    attrs = hass.states.get(STATUS).attributes
    assert attrs["soll_entity"] == SOLL
    assert attrs["hysterese_entity"] == HYST
    assert attrs["regelung_entity"] == REGELUNG
    assert attrs["schalter"] == [PLUG]
    assert attrs["temperatur_sensor"] == SENSOR


async def test_hysterese(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    assert _plug(hass) == STATE_OFF  # Regelung aus -> nichts tun

    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON  # 20.0 < 21.0
    assert hass.states.get(STATUS).state == "heizen"

    await _temp(hass, "21.0")
    assert _plug(hass) == STATE_ON  # Band
    await _temp(hass, "21.5")
    assert _plug(hass) == STATE_ON  # genau Grenze: noch Band (AUS erst > 21.5)
    await _temp(hass, "21.6")
    assert _plug(hass) == STATE_OFF
    assert hass.states.get(STATUS).state == "aus"

    await _temp(hass, "21.2")
    assert _plug(hass) == STATE_OFF  # Band, bleibt aus
    await _temp(hass, "21.0")
    assert _plug(hass) == STATE_OFF  # genau Soll: noch Band (EIN erst < 21.0)
    await _temp(hass, "20.9")
    assert _plug(hass) == STATE_ON


async def test_soll_aenderung_wirkt_sofort(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    await _temp(hass, "22.0")
    await _regelung(hass, True)
    assert _plug(hass) == STATE_OFF
    await _setze(hass, SOLL, 23.0)
    assert _plug(hass) == STATE_ON  # 22 < 23
    await _setze(hass, SOLL, 21.0)
    assert _plug(hass) == STATE_OFF  # 22 > 21.5
    await _setze(hass, HYST, 1.5)
    assert _plug(hass) == STATE_OFF  # Band 21..22.5, halten
    assert hass.states.get(STATUS).attributes["aus_ueber"] == 22.5


async def test_failsafe_sensor(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON
    await _temp(hass, STATE_UNAVAILABLE)
    assert _plug(hass) == STATE_OFF
    assert hass.states.get(STATUS).state == "sensorfehler"
    await _temp(hass, "kaputt")
    assert _plug(hass) == STATE_OFF
    await _temp(hass, "19.0")
    assert _plug(hass) == STATE_ON


async def test_regelung_aus_schaltet_ab_und_laesst_manuell_zu(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON
    await _regelung(hass, False)
    assert _plug(hass) == STATE_OFF
    assert hass.states.get(STATUS).state == "inaktiv"
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": PLUG}, blocking=True)
    await _temp(hass, "25.0")
    assert _plug(hass) == STATE_ON  # inaktiv: kein Eingriff


async def test_manuell_an_ueber_grenze_wird_abgeschaltet(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _temp(hass, "23.0")
    await _anlegen(hass)
    await _regelung(hass, True)
    assert _plug(hass) == STATE_OFF
    await hass.services.async_call("input_boolean", "turn_on", {"entity_id": PLUG}, blocking=True)
    await hass.async_block_till_done()
    assert _plug(hass) == STATE_OFF


async def test_schalter_doppelt_verboten(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    result = await _anlegen(hass, name="Bad")
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_SWITCH: "schalter_belegt"}


async def test_optionen_schalterwechsel(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SENSOR: SENSOR, CONF_SWITCH: [PLUG2], CONF_SENSOR_TIMEOUT: 0}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert _plug(hass) == STATE_OFF  # alter Plug aus
    assert hass.states.get(PLUG2).state == STATE_ON  # neuer regelt (Werte gemerkt)
    assert hass.states.get(REGELUNG).state == STATE_ON


async def test_entfernen_schaltet_aus(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert _plug(hass) == STATE_OFF


async def test_karte_wird_ausgeliefert(hass: HomeAssistant, hass_client) -> None:
    from custom_components.heizregler.const import CARD_URL

    await _basis(hass)
    await _anlegen(hass)
    client = await hass_client()
    resp = await client.get(CARD_URL)
    assert resp.status == 200
    assert "heizregler-card" in await resp.text()


async def test_fehlergrund_attribut(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    await _regelung(hass, True)
    assert hass.states.get(STATUS).attributes["fehler"] is None
    await _temp(hass, STATE_UNAVAILABLE)
    assert "keinen Zahlenwert" in hass.states.get(STATUS).attributes["fehler"]
    await _temp(hass, "20.0")
    assert hass.states.get(STATUS).attributes["fehler"] is None


async def test_climate_entity(hass: HomeAssistant) -> None:
    climate = "climate.hobbykeller"
    await _basis(hass)
    await _anlegen(hass)
    st = hass.states.get(climate)
    assert st is not None
    assert st.state == "off"
    assert st.attributes["hvac_action"] == "off"
    assert st.attributes["temperature"] == 21.0
    assert st.attributes["current_temperature"] == 20.0
    assert hass.states.get(STATUS).attributes["climate_entity"] == climate

    await hass.services.async_call(
        "climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "heat"}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(REGELUNG).state == STATE_ON
    assert _plug(hass) == STATE_ON
    assert hass.states.get(climate).attributes["hvac_action"] == "heating"

    await hass.services.async_call(
        "climate", "set_temperature", {"entity_id": climate, "temperature": 19.0}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(SOLL).state == "19.0"
    assert _plug(hass) == STATE_OFF  # 20 > 19.5
    assert hass.states.get(climate).attributes["hvac_action"] == "idle"

    await hass.services.async_call("climate", "turn_off", {"entity_id": climate}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(REGELUNG).state == STATE_OFF


PLUG3 = "input_boolean.plug3"
PLUG4 = "input_boolean.plug4"


async def test_mehrere_plugs_schalten_gemeinsam(hass: HomeAssistant) -> None:
    await _basis(hass)
    result = await _anlegen(hass, switch=[PLUG, PLUG2, PLUG3])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await _regelung(hass, True)
    for p in (PLUG, PLUG2, PLUG3):
        assert hass.states.get(p).state == STATE_ON
    assert hass.states.get(STATUS).attributes["schalter_an"] == 3
    await _temp(hass, "22.0")
    for p in (PLUG, PLUG2, PLUG3):
        assert hass.states.get(p).state == STATE_OFF
    assert hass.states.get("climate.hobbykeller").attributes["hvac_action"] == "idle"


async def test_ein_plug_weg_andere_regeln_weiter(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass, switch=[PLUG, PLUG2])
    hass.states.async_set(PLUG2, STATE_UNAVAILABLE)
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON
    st = hass.states.get(STATUS)
    assert st.state == "heizen"
    assert "input_boolean.plug2 ist unavailable" in st.attributes["fehler"]
    await _temp(hass, STATE_UNAVAILABLE)
    assert _plug(hass) == STATE_OFF  # Fail-safe auch mit Teil-Ausfall


async def test_alle_plugs_weg(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass, switch=[PLUG, PLUG2])
    hass.states.async_set(PLUG, STATE_UNAVAILABLE)
    hass.states.async_set(PLUG2, STATE_UNAVAILABLE)
    await _regelung(hass, True)
    assert hass.states.get(STATUS).state == "schalterfehler"


async def test_zu_viele_und_ueberschneidung(hass: HomeAssistant) -> None:
    await _basis(hass)
    result = await _anlegen(hass, switch=[PLUG, PLUG2, PLUG3, PLUG4])
    assert result["errors"] == {CONF_SWITCH: "zu_viele_schalter"}
    await _anlegen(hass, switch=[PLUG, PLUG2])
    result = await _anlegen(hass, name="Bad", switch=[PLUG3, PLUG2])
    assert result["errors"] == {CONF_SWITCH: "schalter_belegt"}
    result = await _anlegen(hass, name="Bad", switch=[PLUG3])
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_optionen_plug_entfernen_schaltet_ihn_aus(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass, switch=[PLUG, PLUG2])
    await _regelung(hass, True)
    assert hass.states.get(PLUG2).state == STATE_ON
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SENSOR: SENSOR, CONF_SWITCH: [PLUG], CONF_SENSOR_TIMEOUT: 0}
    )
    await hass.async_block_till_done()
    assert hass.states.get(PLUG2).state == STATE_OFF
    assert _plug(hass) == STATE_ON


async def test_migration_v1(hass: HomeAssistant) -> None:
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    await _basis(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Hobbykeller",
        version=1,
        data={CONF_SENSOR: SENSOR, CONF_SWITCH: PLUG},
        options={CONF_SENSOR_TIMEOUT: 0},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.version == 2
    assert entry.data[CONF_SWITCH] == [PLUG]
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON


async def test_panel_registriert(hass: HomeAssistant, hass_client) -> None:
    from homeassistant.components.frontend import DATA_PANELS

    from custom_components.heizregler.const import PANEL_URL

    await _basis(hass)
    await _anlegen(hass)
    panel = hass.data[DATA_PANELS]["heizregler"]
    assert panel.sidebar_title == "HeatFlow"
    assert panel.config["_panel_custom"]["name"] == "heizregler-panel"
    assert panel.require_admin is False
    client = await hass_client()
    resp = await client.get(PANEL_URL)
    assert resp.status == 200
    assert "heizregler-panel" in await resp.text()


# --------------------------------------------------------------------------- Leistung (0.4.1)

LEISTUNG1 = "sensor.plug1_power"
LEISTUNG2 = "sensor.plug2_power"
LEISTUNG_ENT = "sensor.hobbykeller_leistung"


def _watt(hass, eid, wert, einheit="W"):
    hass.states.async_set(eid, wert, {"device_class": "power", "unit_of_measurement": einheit})


async def test_ohne_leistung_kein_leistungssensor(hass: HomeAssistant) -> None:
    await _basis(hass)
    await _anlegen(hass)
    assert hass.states.get(LEISTUNG_ENT) is None
    attrs = hass.states.get(STATUS).attributes
    assert attrs["leistung"] is None
    assert attrs["leistung_sensoren"] == []


async def test_leistung_summe_und_einheiten(hass: HomeAssistant) -> None:
    await _basis(hass)
    _watt(hass, LEISTUNG1, "1200")
    _watt(hass, LEISTUNG2, "0.8", "kW")
    await _anlegen(hass, switch=[PLUG, PLUG2])
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SENSOR: SENSOR, CONF_SWITCH: [PLUG, PLUG2], CONF_SENSOR_TIMEOUT: 0,
         "leistung_sensoren": [LEISTUNG1, LEISTUNG2]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    st = hass.states.get(LEISTUNG_ENT)
    assert float(st.state) == 2000.0
    assert st.attributes["unit_of_measurement"] == "W"
    assert hass.states.get(STATUS).attributes["leistung"] == 2000.0

    _watt(hass, LEISTUNG1, "0")
    await hass.async_block_till_done()
    assert float(hass.states.get(LEISTUNG_ENT).state) == 800.0

    # ein Sensor weg -> Summe der übrigen
    hass.states.async_set(LEISTUNG2, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert float(hass.states.get(LEISTUNG_ENT).state) == 0.0

    # alle weg -> unavailable
    hass.states.async_set(LEISTUNG1, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get(LEISTUNG_ENT).state == STATE_UNAVAILABLE


async def test_leistung_beeinflusst_regelung_nicht(hass: HomeAssistant) -> None:
    await _basis(hass)
    _watt(hass, LEISTUNG1, "0")
    await _anlegen(hass)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SENSOR: SENSOR, CONF_SWITCH: [PLUG], CONF_SENSOR_TIMEOUT: 0,
         "leistung_sensoren": [LEISTUNG1]},
    )
    await hass.async_block_till_done()
    await _regelung(hass, True)
    assert _plug(hass) == STATE_ON
    _watt(hass, LEISTUNG1, "abc")
    await hass.async_block_till_done()
    assert _plug(hass) == STATE_ON
    assert hass.states.get(STATUS).state == "heizen"


async def _plug_mit_geraet(hass, schalter_uid, leistung_uid):
    """Schalter + Leistungssensor auf einem gemeinsamen Gerät registrieren."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    fremd = MockConfigEntry(domain="test")
    fremd.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=fremd.entry_id, identifiers={("test", schalter_uid)}
    )
    reg = er.async_get(hass)
    sw = reg.async_get_or_create("switch", "test", schalter_uid, device_id=dev.id)
    pw = reg.async_get_or_create(
        "sensor", "test", leistung_uid, device_id=dev.id, original_device_class="power"
    )
    reg.async_get_or_create("sensor", "test", leistung_uid + "_e", device_id=dev.id,
                            original_device_class="energy")
    hass.states.async_set(sw.entity_id, STATE_OFF)
    _watt(hass, pw.entity_id, "1500")
    return sw.entity_id, pw.entity_id


async def test_flow_schlaegt_leistung_vom_plug_vor(hass: HomeAssistant) -> None:
    await _basis(hass)
    sw, pw = await _plug_mit_geraet(hass, "plugA", "plugA_power")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Hobbykeller", CONF_SENSOR: SENSOR, CONF_SWITCH: [sw], CONF_SENSOR_TIMEOUT: 0},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "leistung"
    vorschlag = None
    for key in result["data_schema"].schema:
        if str(key) == "leistung_sensoren":
            vorschlag = key.description["suggested_value"]
    assert vorschlag == [pw]  # nur power, nicht energy

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"leistung_sensoren": [pw]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["leistung_sensoren"] == [pw]
    await hass.async_block_till_done()
    assert float(hass.states.get(LEISTUNG_ENT).state) == 1500.0


async def test_flow_leistung_abgewaehlt(hass: HomeAssistant) -> None:
    await _basis(hass)
    sw, _pw = await _plug_mit_geraet(hass, "plugB", "plugB_power")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Hobbykeller", CONF_SENSOR: SENSOR, CONF_SWITCH: [sw], CONF_SENSOR_TIMEOUT: 0},
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"]["leistung_sensoren"] == []
    await hass.async_block_till_done()
    assert hass.states.get(LEISTUNG_ENT) is None
