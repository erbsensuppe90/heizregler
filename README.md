# Heizregler

[![Tests](https://github.com/erbsensuppe90/heizregler/actions/workflows/tests.yml/badge.svg)](https://github.com/erbsensuppe90/heizregler/actions/workflows/tests.yml)
[![Validate](https://github.com/erbsensuppe90/heizregler/actions/workflows/validate.yml/badge.svg)](https://github.com/erbsensuppe90/heizregler/actions/workflows/validate.yml)

Hysterese-Regler für Home Assistant: ein Temperatursensor steuert 1–3 Schalter/Steckdosen.
Inklusive Thermostat-Karte für das Dashboard.

- **EIN**, wenn Ist < Soll
- **AUS**, wenn Ist > Soll + Hysterese
- dazwischen: Zustand halten
- läuft im HA-Backend, unabhängig davon, ob ein Dashboard offen ist
- Soll, Hysterese und Regelung bleiben über Neustarts erhalten

## Sicherheit

- Sensor `unavailable`/`unknown`/kein Zahlenwert → alle Schalter **AUS**
- optional: Sensor-Timeout → AUS, wenn zu lange kein Wert kommt
- ein Schalter nicht erreichbar → die übrigen regeln weiter, Hinweis im Attribut `fehler`
- Regelung AUS → Schalter einmal AUS, danach kein Eingriff (manuell schaltbar)
- Schalter manuell AN über der Ausschaltgrenze → wird sofort wieder AUS geschaltet
- Regler löschen oder Schalter in den Optionen entfernen → betroffene Schalter AUS
- ein Schalter kann nur zu einem Regler gehören

Empfehlung zusätzlich: am Shelly/Plug selbst einen Auto-Off-Timer und
"Zustand nach Stromausfall = AUS" setzen. Das greift auch, wenn Home Assistant ausfällt.

## Installation über HACS

1. HACS → ⋮ → **Benutzerdefinierte Repositories**
2. Repository: `https://github.com/erbsensuppe90/heizregler`, Typ: **Integration**
3. **Heizregler** suchen → Herunterladen
4. Home Assistant neu starten
5. Browser einmal neu laden (Strg+F5)

Updates erscheinen danach unter Einstellungen → Updates.

## Installation manuell

Ordner `custom_components/heizregler` nach `/config/custom_components/heizregler` kopieren, HA neu starten.

## Einrichtung

1. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → **Heizregler**
2. Name (z.B. Raum), Temperatursensor, 1–3 Schalter wählen
3. Pro Raum wiederholen

Nach dem Anlegen ist die Regelung **AUS**. Soll und Hysterese setzen, dann Regelung einschalten.

Nachträglich ändern: Heizregler → Konfigurieren.

| Option | Bedeutung |
|---|---|
| Temperatursensor | Sensor mit `device_class: temperature` |
| Schalter / Plugs | 1–3 `switch`- oder `input_boolean`-Entities, schalten gemeinsam |
| Sensor-Timeout | Minuten ohne Sensorwert bis AUS. `0` = aus. Nur nutzen, wenn der Sensor auch bei gleichem Wert regelmäßig meldet (z.B. **nicht** bei Homematic IP) |

## Karte

Dashboard → Bearbeiten → Karte hinzufügen → **Heizregler** → Regler wählen.

Die Karte wird von der Integration mitgeliefert, keine Dashboard-Ressource nötig.

```yaml
type: custom:heizregler-card
entity: sensor.hobbykeller_status
name: Hobbykeller   # optional
```

Bedienung: Soll per Bogen ziehen oder −/+, Hysterese und Regelung über die Chips.
Klick auf Ist-Temperatur oder Plug öffnet die jeweilige Entity.

## Entities pro Regler

Beispiel für den Namen "Hobbykeller":

| Entity | Zweck |
|---|---|
| `climate.hobbykeller` | Thermostat: Ist, Soll, Heizen/Aus, Heizt/Leerlauf |
| `number.hobbykeller_soll` | Soll-Temperatur, 5–30 °C, Schritt 0,5 |
| `number.hobbykeller_hysterese` | Hysterese, 0,1–3 K, Schritt 0,1 |
| `switch.hobbykeller_regelung` | Regelung an/aus |
| `sensor.hobbykeller_status` | `heizen` / `aus` / `inaktiv` / `sensorfehler` / `schalterfehler` |

Attribute von `sensor.<name>_status`: `ist_temperatur`, `soll`, `hysterese`, `ein_unter`, `aus_ueber`,
`phase`, `fehler`, `letzte_aktion`, `letzte_schaltung`, `schalter`, `schalter_an`.

## Entwicklung

```bash
python -m venv venv
venv/bin/pip install -r requirements_test.txt
venv/bin/pytest
```

## Lizenz

MIT, siehe [LICENSE](LICENSE).
