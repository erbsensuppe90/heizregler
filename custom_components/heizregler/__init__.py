"""HeatFlow: Hysterese-Regelung Temperatursensor -> Schalter (Domain: heizregler)."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CARD_URL,
    CONF_SWITCH,
    DOMAIN,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL,
    PANEL_URL_PATH,
    PLATFORMS,
    VERSION,
)
from .controller import (
    HeizreglerController,
    async_schalter_aus,
    entry_config,
    schalter_liste,
)

type HeizreglerConfigEntry = ConfigEntry[HeizreglerController]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Karte und Seitenleisten-Panel einmalig ausliefern."""
    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(CARD_URL, str(www / "heizregler-card.js"), cache_headers=False),
            StaticPathConfig(PANEL_URL, str(www / "heizregler-panel.js"), cache_headers=False),
        ]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="heizregler-panel",
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=f"{PANEL_URL}?v={VERSION}",
        config={"card_url": f"{CARD_URL}?v={VERSION}"},
        require_admin=False,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HeizreglerConfigEntry) -> bool:
    """Einen Regler (Raum) einrichten."""
    controller = HeizreglerController(hass, entry)
    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await controller.async_start()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeizreglerConfigEntry) -> bool:
    """Regler entladen."""
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.async_stop()
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """v1 (ein Schalter als String) -> v2 (Liste von Schaltern)."""
    if entry.version > 2:
        return False
    if entry.version == 1:
        data = {**entry.data}
        options = {**entry.options}
        if CONF_SWITCH in data:
            data[CONF_SWITCH] = schalter_liste(data[CONF_SWITCH])
        if CONF_SWITCH in options:
            options[CONF_SWITCH] = schalter_liste(options[CONF_SWITCH])
        hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Regler gelöscht: Schalter sicher AUS lassen."""
    await async_schalter_aus(hass, schalter_liste(entry_config(entry)[CONF_SWITCH]))


async def _async_update_listener(hass: HomeAssistant, entry: HeizreglerConfigEntry) -> None:
    """Optionen geändert: entfernte Schalter AUS, dann neu laden."""
    neu = set(schalter_liste(entry_config(entry)[CONF_SWITCH]))
    entfernt = [eid for eid in entry.runtime_data.switch_ids if eid not in neu]
    await async_schalter_aus(hass, entfernt)
    await hass.config_entries.async_reload(entry.entry_id)
