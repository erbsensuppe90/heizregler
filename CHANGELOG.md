# Changelog

## 0.4.0

- Eigener Menüpunkt **Heizregler** in der Seitenleiste
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
