# Changelog

## 0.4.2

- **Leistung automatisch:** Ist kein Leistungssensor gewählt, nimmt HeatFlow die Leistungssensoren
  der Plug-Geräte automatisch (abschaltbar über „Leistung automatisch vom Plug übernehmen“).
  Bestehende Regler bekommen die Automatik beim Update.
- Leistungsauswahl zeigt alle Sensoren; akzeptiert werden `device_class: power` oder Einheit W/kW/MW/mW.
  Falsche Sensoren werden beim Speichern abgelehnt.
- Neues Attribut `leistung_automatisch` am Status-Sensor
- README: Hinweis zum fehlenden Icon in der HACS-Liste (Fehler in HACS, nicht in HeatFlow)

## 0.4.1

- Optionale **Leistungssensoren** pro Regler (1–3, `device_class: power`, W/kW)
  - beim Anlegen werden die Leistungssensoren der gewählten Plugs automatisch vorgeschlagen
  - nachträglich unter Konfigurieren änderbar
  - neue Entity `sensor.<name>_leistung` (Summe in W), nur wenn Sensoren gewählt sind
- Seitenleiste: Kennzahl **Leistung gesamt** über alle Regler, Spalte „Leistung“ in der Tabelle
- Karte: aktuelle Leistung unter dem Plug-Status
- Leistung dient nur der Anzeige und beeinflusst die Regelung nicht

## 0.4.0

- Neuer Anzeigename **HeatFlow** (Integration, Seitenleiste, Karte). Interner Domain-Name bleibt `heizregler`, bestehende Regler und Entity-IDs bleiben unverändert.
- Eigener Menüpunkt **HeatFlow** in der Seitenleiste
  - Übersicht aller Regler als Kacheln oder Tabelle (Auswahl wird gemerkt)
  - Kennzahlen: Regler, Regelung an, heizen, Plugs an, Fehler
  - „+ Regler“ öffnet direkt die Einrichtung, „Einstellungen“ das Gerät (nur für Admins sichtbar)
  - natives HA-Panel, kein Iframe, kein Token

## 0.3.1

- Eigenes Icon (hell/dunkel) im Ordner `brand/`, wird ab Home Assistant 2026.3 angezeigt

## 0.3.0

- 1–3 Schalter pro Regler, schalten gemeinsam
- Teil-Ausfall: erreichbare Schalter regeln weiter, Hinweis im Attribut `fehler`
- Schalter in den Optionen entfernen → wird vorher AUS geschaltet
- Migration bestehender Regler (ein Schalter → Liste)
- Karte zeigt mehrere Plugs einzeln

## 0.2.0

- `climate`-Entity pro Regler (nativer Thermostat-Dialog)
- Karte neu als Drehregler: Soll per Bogen, Ist-Marker, Hysterese-Band, Plug-Status

## 0.1.1

- Attribut `fehler` mit genauem Grund bei Sensor-/Schalterfehler

## 0.1.0

- Erste Version: Hysterese-Regelung, Config-Flow mit Dropdowns, Karte
