/*
 * Heizregler-Karte (Drehregler)
 * Zeigt einen Heizregler (Integration "heizregler") im Thermostat-Stil:
 * Ist-Temperatur, Plug-Zustand, Soll per Bogen/Knöpfe, Hysterese, Regelung.
 * Die Regel-Logik läuft im HA-Backend, nicht in dieser Karte.
 */
const HZ_VERSION = "0.4.0";

const STATUS_TEXT = {
  start: "Startet",
  heizen: "Heizt",
  aus: "Leerlauf",
  inaktiv: "Aus",
  sensorfehler: "Sensorfehler",
  schalterfehler: "Plug nicht erreichbar",
};

const FARBE_HEIZ = "var(--state-climate-heat-color, #ff8100)";
const FARBE_AUS = "var(--state-inactive-color, #8a8a8a)";
const FARBE_FEHLER = "var(--error-color, #db4437)";

// Bogen-Geometrie (SVG-Einheiten)
const CX = 100;
const CY = 100;
const R = 80;
const START = 135; // Grad, unten links
const SWEEP = 270; // bis unten rechts

function istHeizregler(stateObj) {
  return (
    stateObj &&
    stateObj.entity_id.startsWith("sensor.") &&
    stateObj.attributes.regelung_entity !== undefined &&
    stateObj.attributes.soll_entity !== undefined
  );
}

function liste(wert) {
  if (!wert) return [];
  return Array.isArray(wert) ? wert : [wert];
}

function punkt(grad, r = R) {
  const rad = (grad * Math.PI) / 180;
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)];
}

function bogen(a0, a1) {
  if (!(a1 > a0 + 0.01)) return "";
  const [x0, y0] = punkt(a0);
  const [x1, y1] = punkt(a1);
  const gross = a1 - a0 > 180 ? 1 : 0;
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${R} ${R} 0 ${gross} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

class HeizreglerCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("Bitte einen Heizregler wählen (entity: sensor.<raum>_status)");
    }
    this._config = config;
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 6, min_columns: 6, rows: "auto" };
  }

  static getConfigElement() {
    return document.createElement("heizregler-card-editor");
  }

  static getStubConfig(hass) {
    const e = Object.values(hass.states).find(istHeizregler);
    return { entity: e ? e.entity_id : "" };
  }

  disconnectedCallback() {
    clearTimeout(this._sendTimer);
  }

  // ---------------------------------------------------------------- Helfer
  _lang() {
    return (this._hass && this._hass.locale && this._hass.locale.language) || "de";
  }

  _fmt(wert, nachkomma = 1) {
    if (wert === null || wert === undefined || wert === "" || isNaN(Number(wert))) return "–";
    return Number(wert).toLocaleString(this._lang(), {
      minimumFractionDigits: nachkomma,
      maximumFractionDigits: nachkomma,
    });
  }

  _attr() {
    const st = this._hass && this._config && this._hass.states[this._config.entity];
    return istHeizregler(st) ? st.attributes : null;
  }

  _sollGrenzen() {
    const a = this._attr();
    const n = a && this._hass.states[a.soll_entity];
    return {
      min: n ? Number(n.attributes.min) : 5,
      max: n ? Number(n.attributes.max) : 30,
      step: n ? Number(n.attributes.step) || 0.5 : 0.5,
      wert: n ? Number(n.state) : NaN,
    };
  }

  _winkel(v) {
    const g = this._sollGrenzen();
    const t = Math.min(1, Math.max(0, (v - g.min) / (g.max - g.min)));
    return START + SWEEP * t;
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(
      new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true })
    );
  }

  // ---------------------------------------------------------------- Aufbau
  _aufbauen() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `
      <style>
        :host { --hz-farbe: ${FARBE_AUS}; }
        ha-card { padding: 16px 16px 12px; overflow: hidden; }
        .kopf { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
        .unter { color: var(--secondary-text-color); font-size: 0.85em; }
        .titel { font-size: 1.25em; font-weight: 500; line-height: 1.3; }
        .werte { display: grid; grid-template-columns: 1fr 1fr; text-align: center; margin: 14px 0 4px; }
        .wert { cursor: pointer; border-radius: 8px; padding: 4px; }
        .wert:hover { background: var(--secondary-background-color); }
        .lbl { color: var(--secondary-text-color); font-size: 0.9em; }
        .num { font-size: 1.25em; font-weight: 500; display: flex; align-items: center;
               justify-content: center; gap: 4px; min-height: 1.6em; }
        .num ha-icon { --mdc-icon-size: 20px; }
        .dial { position: relative; width: 100%; max-width: 300px; margin: 4px auto 0; }
        svg { display: block; width: 100%; height: auto; touch-action: none; cursor: pointer;
              user-select: none; -webkit-user-select: none; }
        .track { stroke: var(--secondary-background-color, rgba(127,127,127,0.25)); }
        .aktiv { stroke: var(--hz-farbe); transition: stroke 0.3s; }
        .band { stroke: var(--hz-farbe); opacity: 0.35; }
        .ist { fill: var(--primary-text-color); }
        .daumen { fill: var(--card-background-color, #fff); stroke: var(--hz-farbe); }
        .mitte { position: absolute; left: 0; right: 0; top: 30%; text-align: center;
                 pointer-events: none; }
        .modus { font-weight: 500; font-size: 1em; color: var(--hz-farbe); }
        .soll { display: inline-flex; align-items: flex-start; justify-content: center;
                line-height: 1; margin-top: 4px; }
        .ganz { font-size: 3.6em; font-weight: 400; }
        .rest { display: flex; flex-direction: column; justify-content: space-between;
                font-size: 1.4em; margin-left: 2px; height: 2.3em; }
        .einheit { font-size: 0.75em; padding-top: 4px; }
        .hint { color: var(--secondary-text-color); font-size: 0.85em; margin-top: 6px; }
        .knoepfe { display: flex; justify-content: center; gap: 24px; margin-top: -26px;
                   position: relative; }
        button { font: inherit; color: var(--primary-text-color); cursor: pointer; }
        button:disabled { opacity: 0.35; cursor: default; }
        .rund { width: 48px; height: 48px; border-radius: 50%; background: none;
                border: 1px solid var(--divider-color, rgba(127,127,127,0.5)); font-size: 1.6em;
                display: flex; align-items: center; justify-content: center; padding: 0; }
        .rund:hover:not(:disabled) { background: var(--secondary-background-color); }
        .chips { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 18px; }
        .chip { display: flex; align-items: center; gap: 8px; padding: 6px 10px;
                border-radius: 12px; background: var(--secondary-background-color);
                border: none; text-align: left; min-height: 44px; box-sizing: border-box; }
        .chip ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
        .chip.an ha-icon { color: var(--hz-farbe); }
        .cl { font-size: 0.8em; color: var(--secondary-text-color); line-height: 1.2; }
        .cv { font-size: 0.95em; font-weight: 500; line-height: 1.2; }
        .mini { width: 30px; height: 30px; border-radius: 8px; padding: 0; background: none;
                border: 1px solid var(--divider-color, rgba(127,127,127,0.5)); font-size: 1.1em; }
        .plugs { margin-top: 8px; }
        .plugs:empty { display: none; }
        .plugs .chip { cursor: pointer; min-height: 38px; padding: 4px 10px; }
        .info { text-align: center; color: var(--secondary-text-color); font-size: 0.82em;
                margin-top: 8px; }
        .info:empty { display: none; }
        .fehler { color: ${FARBE_FEHLER}; font-weight: 500; }
        .statuschip { padding: 2px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 500;
                      border: 1px solid var(--hz-farbe); color: var(--hz-farbe); white-space: nowrap; }
      </style>
      <ha-card>
        <div class="kopf">
          <div>
            <div class="unter">Heizregler</div>
            <div class="titel"></div>
          </div>
        </div>
        <div class="werte">
          <div class="wert" data-more="sensor">
            <div class="lbl">Ist-Temperatur</div>
            <div class="num ist-wert"></div>
          </div>
          <div class="wert" data-more="plug">
            <div class="lbl plug-lbl">Plug</div>
            <div class="num plug-wert"><ha-icon></ha-icon><span></span></div>
          </div>
        </div>
        <div class="dial">
          <svg viewBox="0 0 200 172" role="slider" aria-label="Soll-Temperatur">
            <path class="track" fill="none" stroke-width="14" stroke-linecap="round"></path>
            <path class="aktiv" fill="none" stroke-width="14" stroke-linecap="round"></path>
            <path class="band" fill="none" stroke-width="14"></path>
            <circle class="ist" r="3.5"></circle>
            <circle class="daumen" r="9" stroke-width="4"></circle>
          </svg>
          <div class="mitte">
            <div class="modus"></div>
            <div class="soll"><span class="ganz"></span><span class="rest"><span class="einheit">°C</span><span class="dez"></span></span></div>
            <div class="hint"></div>
          </div>
        </div>
        <div class="knoepfe">
          <button class="rund minus" aria-label="Soll verringern">−</button>
          <button class="rund plus" aria-label="Soll erhöhen">+</button>
        </div>
        <div class="chips">
          <button class="chip regelung" aria-label="Regelung umschalten">
            <ha-icon icon="mdi:thermostat-auto"></ha-icon>
            <div><div class="cl">Regelung</div><div class="cv regelung-wert"></div></div>
          </button>
          <div class="chip hyst">
            <ha-icon icon="mdi:arrow-expand-vertical"></ha-icon>
            <div><div class="cl">Hysterese</div><div class="cv hyst-wert"></div></div>
            <button class="mini" data-d="-1" aria-label="Hysterese verringern">−</button>
            <button class="mini" data-d="1" aria-label="Hysterese erhöhen">+</button>
          </div>
        </div>
        <div class="chips plugs"></div>
        <div class="info fehler"></div>
        <div class="info aktion"></div>
      </ha-card>`;

    const $ = (s) => root.querySelector(s);
    this._el = {
      titel: $(".titel"),
      ist: $(".ist-wert"),
      plugIcon: $(".plug-wert ha-icon"),
      plugText: $(".plug-wert span"),
      plugLbl: $(".plug-lbl"),
      plugs: $(".plugs"),
      svg: $("svg"),
      track: $(".track"),
      aktiv: $(".aktiv"),
      band: $(".band"),
      istPunkt: $("circle.ist"),
      daumen: $(".daumen"),
      modus: $(".modus"),
      ganz: $(".ganz"),
      dez: $(".dez"),
      hint: $(".hint"),
      minus: $(".minus"),
      plus: $(".plus"),
      regelung: $(".regelung"),
      regelungWert: $(".regelung-wert"),
      hystWert: $(".hyst-wert"),
      hystBtns: root.querySelectorAll(".hyst .mini"),
      fehler: $(".fehler"),
      aktion: $(".aktion"),
    };

    this._el.track.setAttribute("d", bogen(START, START + SWEEP));

    root.querySelectorAll("[data-more]").forEach((el) =>
      el.addEventListener("click", () => {
        const a = this._attr();
        if (!a) return;
        const plugs = liste(a.schalter);
        if (el.dataset.more === "sensor") this._moreInfo(a.temperatur_sensor);
        else if (plugs.length === 1) this._moreInfo(plugs[0]);
      })
    );
    this._el.minus.addEventListener("click", () => this._sollSchritt(-1));
    this._el.plus.addEventListener("click", () => this._sollSchritt(1));
    this._el.regelung.addEventListener("click", () => this._toggleRegelung());
    this._el.hystBtns.forEach((b) =>
      b.addEventListener("click", () => this._hystSchritt(Number(b.dataset.d)))
    );
    this._dragEinrichten();
  }

  // ---------------------------------------------------------------- Bedienung
  _dragEinrichten() {
    const svg = this._el.svg;
    const ausPointer = (ev) => {
      const rect = svg.getBoundingClientRect();
      const s = 200 / rect.width;
      const x = (ev.clientX - rect.left) * s - CX;
      const y = (ev.clientY - rect.top) * s - CY;
      let grad = (Math.atan2(y, x) * 180) / Math.PI;
      if (grad < 0) grad += 360;
      let rel = (grad - START + 360) % 360;
      if (rel > SWEEP) rel = rel > SWEEP + (360 - SWEEP) / 2 ? 0 : SWEEP;
      const g = this._sollGrenzen();
      let v = g.min + (rel / SWEEP) * (g.max - g.min);
      v = Math.round(v / g.step) * g.step;
      return Number(Math.min(g.max, Math.max(g.min, v)).toFixed(2));
    };
    svg.addEventListener("pointerdown", (ev) => {
      if (!this._attr() || this._sollGesperrt()) return;
      this._ziehen = true;
      svg.setPointerCapture(ev.pointerId);
      this._sollVormerken(ausPointer(ev), false);
    });
    svg.addEventListener("pointermove", (ev) => {
      if (!this._ziehen) return;
      this._sollVormerken(ausPointer(ev), false);
    });
    const ende = () => {
      if (!this._ziehen) return;
      this._ziehen = false;
      this._sollSenden(400);
    };
    svg.addEventListener("pointerup", ende);
    svg.addEventListener("pointercancel", ende);
  }

  _sollGesperrt() {
    const a = this._attr();
    const n = a && this._hass.states[a.soll_entity];
    return !n || n.state === "unavailable";
  }

  _sollAktuell() {
    return this._pendingSoll !== undefined && this._pendingSoll !== null
      ? this._pendingSoll
      : this._sollGrenzen().wert;
  }

  _sollSchritt(richtung) {
    const g = this._sollGrenzen();
    if (isNaN(g.wert)) return;
    let v = this._sollAktuell() + richtung * g.step;
    v = Math.round(v / g.step) * g.step;
    v = Number(Math.min(g.max, Math.max(g.min, v)).toFixed(2));
    this._sollVormerken(v, true);
  }

  _sollVormerken(v, senden) {
    this._pendingSoll = v;
    this._pendingSeit = Date.now();
    this._update();
    if (senden) this._sollSenden(800);
  }

  _sollSenden(verzoegerung) {
    clearTimeout(this._sendTimer);
    this._sendTimer = setTimeout(() => {
      const a = this._attr();
      if (!a || this._pendingSoll === undefined || this._pendingSoll === null) return;
      const wert = this._pendingSoll;
      this._pendingSeit = Date.now();
      if (a.climate_entity && this._hass.states[a.climate_entity]) {
        this._hass.callService("climate", "set_temperature", {
          entity_id: a.climate_entity,
          temperature: wert,
        });
      } else {
        this._hass.callService("number", "set_value", { entity_id: a.soll_entity, value: wert });
      }
    }, verzoegerung);
  }

  _hystSchritt(richtung) {
    const a = this._attr();
    const n = a && this._hass.states[a.hysterese_entity];
    if (!n) return;
    const step = Number(n.attributes.step) || 0.1;
    let v = Number(n.state) + richtung * step;
    v = Math.round(v / step) * step;
    v = Number(Math.min(Number(n.attributes.max), Math.max(Number(n.attributes.min), v)).toFixed(2));
    this._hass.callService("number", "set_value", { entity_id: a.hysterese_entity, value: v });
  }

  _toggleRegelung() {
    const a = this._attr();
    if (!a || !a.regelung_entity) return;
    this._hass.callService("switch", "toggle", { entity_id: a.regelung_entity });
  }

  // ---------------------------------------------------------------- Anzeige
  _plugChips(plugInfo) {
    const box = this._el.plugs;
    const key = plugInfo.map((p) => p.id).join("|");
    if (box.dataset.key !== key) {
      box.dataset.key = key;
      box.innerHTML = "";
      plugInfo.forEach((p) => {
        const chip = document.createElement("button");
        chip.className = "chip";
        chip.innerHTML = `<ha-icon></ha-icon><div><div class="cl"></div><div class="cv"></div></div>`;
        chip.addEventListener("click", () => this._moreInfo(p.id));
        box.appendChild(chip);
      });
    }
    plugInfo.forEach((p, i) => {
      const chip = box.children[i];
      const icon = chip.querySelector("ha-icon");
      icon.setAttribute("icon", !p.ok ? "mdi:power-plug-off-outline" : p.an ? "mdi:power-plug" : "mdi:power-plug-off");
      icon.style.color = !p.ok ? FARBE_FEHLER : p.an ? FARBE_HEIZ : "var(--secondary-text-color)";
      chip.querySelector(".cl").textContent = p.name;
      chip.querySelector(".cv").textContent = !p.ok ? "n/a" : p.an ? "AN" : "AUS";
    });
  }

  _update() {
    if (!this._hass || !this._config) return;
    if (!this.shadowRoot) this._aufbauen();
    const e = this._el;

    const st = this._hass.states[this._config.entity];
    if (!istHeizregler(st)) {
      e.titel.textContent = this._config.name || "Heizregler";
      e.fehler.textContent = `Entity ${this._config.entity} ist kein Heizregler-Status-Sensor.`;
      return;
    }
    const a = st.attributes;
    const status = st.state;
    const g = this._sollGrenzen();

    // vorgemerkter Soll erledigt, sobald HA ihn meldet (oder nach 5 s)
    if (
      this._pendingSoll !== undefined &&
      this._pendingSoll !== null &&
      !this._ziehen &&
      (Math.abs(g.wert - this._pendingSoll) < 0.001 || Date.now() - (this._pendingSeit || 0) > 5000)
    ) {
      this._pendingSoll = null;
    }
    const soll = this._sollAktuell();
    const reg = a.regelung_entity && this._hass.states[a.regelung_entity];
    const regAn = reg && reg.state === "on";
    const hystN = a.hysterese_entity && this._hass.states[a.hysterese_entity];
    const hyst = hystN ? Number(hystN.state) : Number(a.hysterese);

    const fehler = status === "sensorfehler" || status === "schalterfehler";
    const farbe = fehler ? FARBE_FEHLER : regAn ? FARBE_HEIZ : FARBE_AUS;
    this.style.setProperty("--hz-farbe", farbe);

    const name = (a.friendly_name || "").replace(/\s*Status$/, "");
    e.titel.textContent = this._config.name || name || "Heizregler";

    // Ist + Plug
    e.ist.textContent = `${this._fmt(a.ist_temperatur)} °C`;
    const plugIds = liste(a.schalter);
    const plugInfo = plugIds.map((id) => {
      const p = this._hass.states[id];
      const ok = !!p && p.state !== "unavailable" && p.state !== "unknown";
      return {
        id,
        ok,
        an: ok && p.state === "on",
        name: (p && p.attributes.friendly_name) || id,
      };
    });
    const anzahlAn = plugInfo.filter((p) => p.an).length;
    const alleOk = plugInfo.length > 0 && plugInfo.every((p) => p.ok);
    const keinerOk = !plugInfo.some((p) => p.ok);
    e.plugLbl.textContent = plugInfo.length > 1 ? "Plugs" : "Plug";
    e.plugIcon.setAttribute(
      "icon",
      keinerOk ? "mdi:power-plug-off-outline" : anzahlAn ? "mdi:power-plug" : "mdi:power-plug-off"
    );
    e.plugIcon.style.color = keinerOk
      ? FARBE_FEHLER
      : anzahlAn
        ? FARBE_HEIZ
        : "var(--secondary-text-color)";
    if (plugInfo.length <= 1) {
      e.plugText.textContent = keinerOk ? "n/a" : anzahlAn ? "AN" : "AUS";
    } else {
      e.plugText.textContent = `${anzahlAn}/${plugInfo.length} AN${alleOk ? "" : " !"}`;
    }
    this._plugChips(plugInfo.length > 1 ? plugInfo : []);

    // Bogen
    const wSoll = this._winkel(isNaN(soll) ? g.min : soll);
    e.aktiv.setAttribute("d", regAn || fehler ? bogen(START, wSoll) : "");
    e.band.setAttribute("d", regAn ? bogen(wSoll, this._winkel(soll + (isNaN(hyst) ? 0 : hyst))) : "");
    const [dx, dy] = punkt(wSoll);
    e.daumen.setAttribute("cx", dx.toFixed(2));
    e.daumen.setAttribute("cy", dy.toFixed(2));
    const ist = Number(a.ist_temperatur);
    if (a.ist_temperatur === null || a.ist_temperatur === undefined || isNaN(ist)) {
      e.istPunkt.style.display = "none";
    } else {
      const [ix, iy] = punkt(this._winkel(ist));
      e.istPunkt.style.display = "";
      e.istPunkt.setAttribute("cx", ix.toFixed(2));
      e.istPunkt.setAttribute("cy", iy.toFixed(2));
    }
    e.svg.setAttribute("aria-valuenow", String(soll));

    // Mitte
    e.modus.textContent = STATUS_TEXT[status] || status;
    const txt = this._fmt(soll);
    const m = txt.match(/^(-?\d+)(\D)(\d+)$/);
    e.ganz.textContent = m ? m[1] : txt;
    e.dez.textContent = m ? m[2] + m[3] : "";
    e.hint.textContent = isNaN(hyst) ? "" : `AUS über ${this._fmt(soll + hyst)} °C`;

    // Knöpfe
    const gesperrt = this._sollGesperrt();
    e.minus.disabled = gesperrt || soll <= g.min;
    e.plus.disabled = gesperrt || soll >= g.max;

    // Chips
    e.regelung.classList.toggle("an", !!regAn);
    e.regelung.disabled = !reg || reg.state === "unavailable";
    e.regelungWert.textContent = regAn ? "An" : "Aus";
    e.hystWert.textContent = isNaN(hyst) ? "–" : `${this._fmt(hyst)} K`;
    if (hystN) {
      e.hystBtns[0].disabled = hyst <= Number(hystN.attributes.min);
      e.hystBtns[1].disabled = hyst >= Number(hystN.attributes.max);
    }

    // Info
    e.fehler.textContent = a.fehler || "";
    let aktion = "";
    if (a.letzte_aktion) {
      const zeit = a.letzte_schaltung
        ? new Date(a.letzte_schaltung).toLocaleString(this._lang(), {
            day: "2-digit",
            month: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
          })
        : "";
      aktion = `Zuletzt: ${a.letzte_aktion}${zeit ? " (" + zeit + ")" : ""}`;
    }
    e.aktion.textContent = aktion;
  }
}

class HeizreglerCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) =>
        ({ entity: "Heizregler", name: "Titel (optional)" })[s.name] || s.name;
      this._form.addEventListener("value-changed", (ev) => {
        this._config = ev.detail.value;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config: this._config },
            bubbles: true,
            composed: true,
          })
        );
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = [
      {
        name: "entity",
        required: true,
        selector: { entity: { filter: { integration: "heizregler", domain: "sensor" } } },
      },
      { name: "name", selector: { text: {} } },
    ];
    this._form.data = this._config;
  }
}

if (!customElements.get("heizregler-card")) {
  customElements.define("heizregler-card", HeizreglerCard);
  customElements.define("heizregler-card-editor", HeizreglerCardEditor);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "heizregler-card",
    name: "Heizregler",
    description: "Thermostat-Karte: Soll, Hysterese, Regelung und Plug-Status",
    preview: true,
  });
  console.info(`%c HEIZREGLER-CARD %c v${HZ_VERSION} `, "background:#ff8100;color:#fff", "");
}
