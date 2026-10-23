/*
 * HeatFlow-Panel (Seitenleiste)
 * Übersicht aller Heizregler als Kacheln oder Tabelle.
 * Natives HA-Panel: bekommt `hass` direkt vom Frontend, kein Token, kein Iframe.
 * Die Regel-Logik läuft im HA-Backend, nicht hier.
 */
const HZP_VERSION = "0.4.3";

const STATUS_TEXT = {
  start: "Startet",
  heizen: "Heizt",
  aus: "Leerlauf",
  inaktiv: "Aus",
  sensorfehler: "Sensorfehler",
  schalterfehler: "Plug nicht erreichbar",
};
const FARBE_HEIZ = "var(--state-climate-heat-color, #ff8100)";
const FARBE_AUS = "var(--secondary-text-color)";
const FARBE_FEHLER = "var(--error-color, #db4437)";
const SPEICHER_ANSICHT = "heizregler_panel_ansicht";

function istHeizregler(st) {
  return (
    st &&
    st.entity_id.startsWith("sensor.") &&
    st.attributes.regelung_entity !== undefined &&
    st.attributes.soll_entity !== undefined
  );
}

function liste(w) {
  if (!w) return [];
  return Array.isArray(w) ? w : [w];
}

function navigate(pfad) {
  history.pushState(null, "", pfad);
  window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function farbeFuer(status, regelungAn) {
  if (status === "sensorfehler" || status === "schalterfehler") return FARBE_FEHLER;
  if (status === "heizen") return FARBE_HEIZ;
  return regelungAn ? "var(--primary-text-color)" : FARBE_AUS;
}

class HeizreglerPanel extends HTMLElement {
  constructor() {
    super();
    this._cards = new Map();
    this._ansicht = "kacheln";
    try {
      const v = localStorage.getItem(SPEICHER_ANSICHT);
      if (v === "kacheln" || v === "tabelle") this._ansicht = v;
    } catch (_e) {
      /* Speicher nicht verfügbar */
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menu) this._menu.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
    this._ladeKarte();
  }

  set route(_r) {}

  // ---------------------------------------------------------------- Daten
  _regler() {
    if (!this._hass) return [];
    return Object.values(this._hass.states)
      .filter(istHeizregler)
      .map((st) => {
        const a = st.attributes;
        const reg = this._hass.states[a.regelung_entity];
        const plugs = liste(a.schalter).map((id) => {
          const p = this._hass.states[id];
          const ok = !!p && p.state !== "unavailable" && p.state !== "unknown";
          return { id, ok, an: ok && p.state === "on", name: (p && p.attributes.friendly_name) || id };
        });
        const ent = this._hass.entities && this._hass.entities[st.entity_id];
        return {
          id: st.entity_id,
          name: (a.friendly_name || st.entity_id).replace(/\s*Status$/, ""),
          status: st.state,
          regelungAn: !!reg && reg.state === "on",
          ist: a.ist_temperatur,
          soll: a.soll,
          hyst: a.hysterese,
          ausUeber: a.aus_ueber,
          fehler: a.fehler,
          letzte: a.letzte_aktion,
          letzteZeit: a.letzte_schaltung,
          plugs,
          climate: a.climate_entity,
          leistung: typeof a.leistung === "number" ? a.leistung : null,
          hatLeistung: liste(a.leistung_sensoren).length > 0,
          deviceId: ent ? ent.device_id : null,
        };
      })
      .sort((x, y) => x.name.localeCompare(y.name, "de"));
  }

  _istAdmin() {
    return !!(this._hass && this._hass.user && this._hass.user.is_admin);
  }

  _lang() {
    return (this._hass && this._hass.locale && this._hass.locale.language) || "de";
  }

  _fmt(w, n = 1) {
    if (w === null || w === undefined || w === "" || isNaN(Number(w))) return "–";
    return Number(w).toLocaleString(this._lang(), { minimumFractionDigits: n, maximumFractionDigits: n });
  }

  _watt(w) {
    if (w === null || w === undefined || isNaN(Number(w))) return "–";
    const v = Number(w);
    if (Math.abs(v) >= 1000) return `${this._fmt(v / 1000, 2)} kW`;
    return `${this._fmt(v, 0)} W`;
  }

  _zeit(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString(this._lang(), {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  _ladeKarte() {
    if (customElements.get("heizregler-card")) return;
    // Sobald die Karte definiert ist (egal von wo geladen): Platzhalter ersetzen
    if (!this._wartetAufKarte) {
      this._wartetAufKarte = true;
      customElements.whenDefined("heizregler-card").then(() => {
        this._karteFehler = null;
        this._render();
      });
    }
    if (this._karteLaedt) return;
    const url =
      (this._panel && this._panel.config && this._panel.config.card_url) ||
      `/heizregler_static/heizregler-card.js?v=${HZP_VERSION}`;
    this._karteLaedt = true;
    import(url)
      .catch((err) => {
        console.error("HeatFlow: Karte konnte nicht geladen werden", url, err);
        this._karteFehler = String((err && err.message) || err);
        // Rückfallebene: als normales Modul-Script einhängen
        const sc = document.createElement("script");
        sc.type = "module";
        sc.src = url;
        document.head.appendChild(sc);
      })
      .finally(() => {
        this._karteLaedt = false;
        this._render();
      });
  }

  // ---------------------------------------------------------------- Aufbau
  _aufbauen() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { display: block; min-height: 100vh; background: var(--primary-background-color);
                color: var(--primary-text-color); font-family: var(--paper-font-body1_-_font-family, inherit); }
        .bar { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 8px;
               height: var(--header-height, 56px); padding: 0 12px;
               background: var(--app-header-background-color, var(--primary-background-color));
               color: var(--app-header-text-color, var(--primary-text-color));
               border-bottom: var(--app-header-border-bottom, 1px solid var(--divider-color)); box-sizing: border-box; }
        .bar .titel { font-size: 20px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .inhalt { padding: 16px; max-width: 1400px; margin: 0 auto; box-sizing: border-box; }
        .kopf { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-bottom: 16px; }
        .kpis { display: flex; flex-wrap: wrap; gap: 8px; flex: 1; }
        .kpi { background: var(--card-background-color); border-radius: 12px; padding: 8px 14px;
               border: 1px solid var(--divider-color); min-width: 92px; }
        .kpi .z { font-size: 1.4em; font-weight: 500; line-height: 1.2; }
        .kpi .l { font-size: 0.8em; color: var(--secondary-text-color); }
        .kpi.heiz .z { color: ${FARBE_HEIZ}; }
        .kpi.fehler .z { color: ${FARBE_FEHLER}; }
        .kpi.leistung .z { color: ${FARBE_HEIZ}; }
        .umschalter { display: inline-flex; border: 1px solid var(--divider-color); border-radius: 10px; overflow: hidden; }
        .umschalter button { border: 0; background: none; padding: 8px 14px; cursor: pointer; font: inherit;
                             color: var(--secondary-text-color); }
        .umschalter button.an { background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .neu { border: 0; border-radius: 10px; padding: 9px 16px; cursor: pointer; font: inherit; font-weight: 500;
               background: var(--primary-color); color: var(--text-primary-color, #fff); }
        .grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); align-items: start; }
        .zelle { display: flex; flex-direction: column; gap: 6px; }
        .links { display: flex; justify-content: flex-end; gap: 4px; }
        .link { border: 0; background: none; color: var(--primary-color); cursor: pointer; font: inherit;
                font-size: 0.9em; padding: 4px 8px; border-radius: 6px; }
        .link:hover { background: var(--secondary-background-color); }
        .tabwrap { background: var(--card-background-color); border-radius: 12px; border: 1px solid var(--divider-color);
                   overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; font-size: 0.95em; }
        th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--divider-color); white-space: nowrap; }
        th { font-weight: 500; color: var(--secondary-text-color); font-size: 0.85em; }
        tr:last-child td { border-bottom: 0; }
        tbody tr { cursor: pointer; }
        tbody tr:hover { background: var(--secondary-background-color); }
        td.num { text-align: right; font-variant-numeric: tabular-nums; }
        th.num { text-align: right; }
        .st { font-weight: 500; }
        .klein { color: var(--secondary-text-color); font-size: 0.85em; white-space: normal; }
        .rot { color: ${FARBE_FEHLER}; }
        .plugs span { display: inline-block; margin-right: 6px; }
        .leer { text-align: center; padding: 48px 16px; color: var(--secondary-text-color); }
        .leer .gross { font-size: 1.2em; color: var(--primary-text-color); margin-bottom: 8px; }
        @media (max-width: 600px) {
          .inhalt { padding: 8px; }
          .grid { grid-template-columns: 1fr; }
          .kpis { flex: 1 1 100%; display: grid; grid-template-columns: repeat(3, 1fr); }
          .kpi { min-width: 0; padding: 6px 10px; }
          .umschalter { flex: 1; }
          .umschalter button { flex: 1; }
        }
      </style>
      <div class="bar"><span class="menu"></span><div class="titel">HeatFlow</div></div>
      <div class="inhalt">
        <div class="kopf">
          <div class="kpis"></div>
          <div class="umschalter">
            <button data-a="kacheln">Kacheln</button><button data-a="tabelle">Tabelle</button>
          </div>
          <button class="neu">+ Regler</button>
        </div>
        <div class="grid"></div>
        <div class="tabwrap"></div>
        <div class="leer"></div>
      </div>`;
    const $ = (s) => root.querySelector(s);
    this._kpis = $(".kpis");
    this._grid = $(".grid");
    this._tab = $(".tabwrap");
    this._leer = $(".leer");
    this._neu = $(".neu");
    this._umschalter = root.querySelectorAll(".umschalter button");

    if (customElements.get("ha-menu-button")) {
      this._menu = document.createElement("ha-menu-button");
      this._menu.narrow = this._narrow;
      $(".menu").appendChild(this._menu);
    }
    this._umschalter.forEach((b) =>
      b.addEventListener("click", () => {
        this._ansicht = b.dataset.a;
        try {
          localStorage.setItem(SPEICHER_ANSICHT, this._ansicht);
        } catch (_e) {
          /* egal */
        }
        this._render();
      })
    );
    this._neu.addEventListener("click", () => navigate("/config/integrations/dashboard/add?domain=heizregler"));
    this._tab.addEventListener("click", (ev) => {
      const tr = ev.target.closest("tr[data-id]");
      if (tr) this._moreInfo(tr.dataset.id);
    });
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }

  // ---------------------------------------------------------------- Anzeige
  _render() {
    if (!this._hass) return;
    if (!this.shadowRoot) this._aufbauen();
    if (this._menu) this._menu.hass = this._hass;

    const regler = this._regler();
    const admin = this._istAdmin();
    this._neu.style.display = admin ? "" : "none";
    this._umschalter.forEach((b) => b.classList.toggle("an", b.dataset.a === this._ansicht));

    // Kennzahlen
    const heizen = regler.filter((r) => r.status === "heizen").length;
    const fehler = regler.filter((r) => r.status === "sensorfehler" || r.status === "schalterfehler" || r.fehler).length;
    const aktiv = regler.filter((r) => r.regelungAn).length;
    const plugsAn = regler.reduce((s, r) => s + r.plugs.filter((p) => p.an).length, 0);
    const plugsGes = regler.reduce((s, r) => s + r.plugs.length, 0);
    const mitLeistung = regler.filter((r) => r.hatLeistung);
    const leistungGes = mitLeistung.reduce((s, r) => s + (r.leistung || 0), 0);
    const leistungKpi = mitLeistung.length
      ? `<div class="kpi leistung" title="Summe aus ${mitLeistung.length} von ${regler.length} Reglern mit Leistungsmessung">
           <div class="z">${this._watt(leistungGes)}</div><div class="l">Leistung gesamt</div></div>`
      : "";
    this._kpis.innerHTML = `
      <div class="kpi"><div class="z">${regler.length}</div><div class="l">Regler</div></div>
      <div class="kpi"><div class="z">${aktiv}</div><div class="l">Regelung an</div></div>
      <div class="kpi heiz"><div class="z">${heizen}</div><div class="l">heizen</div></div>
      <div class="kpi"><div class="z">${plugsAn}/${plugsGes}</div><div class="l">Plugs an</div></div>
      <div class="kpi ${fehler ? "fehler" : ""}"><div class="z">${fehler}</div><div class="l">mit Fehler</div></div>
      ${leistungKpi}`;

    // Leerzustand
    if (!regler.length) {
      this._grid.style.display = "none";
      this._tab.style.display = "none";
      this._leer.style.display = "";
      this._leer.innerHTML = `<div class="gross">Noch kein Heizregler angelegt.</div>
        ${admin ? "Oben rechts auf „+ Regler“ klicken." : "Ein Administrator kann Regler anlegen."}`;
      return;
    }
    this._leer.style.display = "none";

    if (this._ansicht === "tabelle") {
      this._grid.style.display = "none";
      this._tab.style.display = "";
      this._renderTabelle(regler);
    } else {
      this._tab.style.display = "none";
      this._grid.style.display = "";
      this._renderKacheln(regler, admin);
    }
  }

  _renderKacheln(regler, admin) {
    const karteDa = !!customElements.get("heizregler-card");
    if (!karteDa) this._ladeKarte();
    const ids = new Set(regler.map((r) => r.id));
    for (const [id, z] of this._cards) {
      if (!ids.has(id)) {
        z.el.remove();
        this._cards.delete(id);
      }
    }
    regler.forEach((r, i) => {
      let z = this._cards.get(r.id);
      if (z && karteDa && !z.card) {
        // Platzhalter durch echte Karte ersetzen
        z.el.remove();
        this._cards.delete(r.id);
        z = undefined;
      }
      if (!z) {
        const el = document.createElement("div");
        el.className = "zelle";
        let card = null;
        if (karteDa) {
          card = document.createElement("heizregler-card");
          card.setConfig({ entity: r.id });
          el.appendChild(card);
        } else {
          const p = document.createElement("div");
          p.className = "klein";
          p.textContent = this._karteFehler
            ? `${r.name}: Karte konnte nicht geladen werden (${this._karteFehler}). Seite neu laden (Strg+F5).`
            : `${r.name}: Karte wird geladen …`;
          el.appendChild(p);
        }
        const links = document.createElement("div");
        links.className = "links";
        links.innerHTML = `<button class="link verlauf">Verlauf</button><button class="link einst">Einstellungen</button>`;
        links.querySelector(".verlauf").addEventListener("click", () => this._moreInfo(this._cards.get(r.id).climate || r.id));
        links.querySelector(".einst").addEventListener("click", () => {
          const d = this._cards.get(r.id).deviceId;
          navigate(d ? `/config/devices/device/${d}` : "/config/integrations/integration/heizregler");
        });
        el.appendChild(links);
        z = { el, card, links };
        this._cards.set(r.id, z);
      }
      z.climate = r.climate;
      z.deviceId = r.deviceId;
      z.links.querySelector(".einst").style.display = admin ? "" : "none";
      if (z.card) z.card.hass = this._hass;
      if (this._grid.children[i] !== z.el) this._grid.insertBefore(z.el, this._grid.children[i] || null);
    });
  }

  _renderTabelle(regler) {
    const zeilen = regler
      .map((r) => {
        const farbe = farbeFuer(r.status, r.regelungAn);
        const plugs = r.plugs
          .map((p) => {
            const c = !p.ok ? FARBE_FEHLER : p.an ? FARBE_HEIZ : FARBE_AUS;
            return `<span style="color:${c}">● ${esc(p.name)}</span>`;
          })
          .join("");
        const fehler = r.fehler ? `<div class="klein rot">${esc(r.fehler)}</div>` : "";
        const letzte = r.letzte ? `${esc(r.letzte)}<br>${esc(this._zeit(r.letzteZeit))}` : "–";
        return `<tr data-id="${esc(r.climate || r.id)}">
          <td><div>${esc(r.name)}</div>${fehler}</td>
          <td class="st" style="color:${farbe}">${esc(STATUS_TEXT[r.status] || r.status)}</td>
          <td>${r.regelungAn ? "An" : "Aus"}</td>
          <td class="num">${this._fmt(r.ist)} °C</td>
          <td class="num">${this._fmt(r.soll)} °C</td>
          <td class="num">${this._fmt(r.hyst)} K</td>
          <td class="num">${this._fmt(r.ausUeber)} °C</td>
          <td class="plugs">${plugs}</td>
          <td class="num">${r.hatLeistung ? this._watt(r.leistung) : "–"}</td>
          <td class="klein">${letzte}</td>
        </tr>`;
      })
      .join("");
    this._tab.innerHTML = `<table>
      <thead><tr><th>Regler</th><th>Status</th><th>Regelung</th><th class="num">Ist</th><th class="num">Soll</th>
      <th class="num">Hysterese</th><th class="num">AUS über</th><th>Plugs</th><th class="num">Leistung</th><th>Letzte Schaltung</th></tr></thead>
      <tbody>${zeilen}</tbody></table>`;
  }
}

if (!customElements.get("heizregler-panel")) {
  customElements.define("heizregler-panel", HeizreglerPanel);
  console.info(`%c HEIZREGLER-PANEL %c v${HZP_VERSION} `, "background:#ff8100;color:#fff", "");
}
