# Roadmap

## 0.4.2 (geplant)

- [ ] **Icon in HACS**: In Home Assistant (Geräte & Dienste) wird das Icon aus `brand/` angezeigt,
      in der HACS-Liste steht aber "icon not available". Ursache prüfen (HACS lädt Icons vermutlich
      nicht über den lokalen `brand/`-Ordner) und beheben.

## Später

- [ ] PV-Überschuss-Modus (nur heizen bzw. höheren Soll, wenn Einspeisung > X W)
- [ ] Sicherheit: Max-Laufzeit am Stück, absolute Max-Temperatur, Meldung bei Fehler
- [ ] Zeitplan / Absenkung (Komfort/Eco)
- [ ] Gestaffelte Plugs (Plug 2/3 erst bei größerer Abweichung)
- [ ] Repo-Umbenennung `heizregler` → `heatflow` (Links in manifest.json/README anpassen)
