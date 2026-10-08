# Produktions-Tracking (Zeit / Aufwand)

Session-Board für parallele **Produktionsläufe** mit **Prozessen** darunter (voraus/live/nachträglich), getrennten Zeitspuren Arbeitszeit und Maschinenzeit, Multi-Select Produkte **und** Familien am Lauf, Mengen an Lauf und Prozess. Schätzung + Messung je Prozess (Messung bevorzugt für Anzeige/Kosten). Maschinen-Stammdaten (Name, Notiz, Leistung W), Stundensatz-Katalog mit Default am User, globaler Stromtarif. Produktkosten pro Typ: aktuell Ø Zeiten × heutige Tarife; Historie als Snapshot nach Lauf-Abschluss für **alle** verknüpften Produkttypen denselben Satz; Familienansicht filterbar mit Durchschnitt bei abweichenden Preisen. Entkoppelt von Fertigen/Lagerbuchung. Kein Shopify-Write, keine Vorlagen/Gemini, kein Material-/Werkzeug-Verschleiß in Slice 1–2.

**Status:** accepted (Slice 1 live; Slice 2 Nesting/Multi/Zeiten/Kosten)

**Considered Options:** Nur Timer ohne Kosten; ein Stundensatz; Timing = Fertigen; Menge nur am Lauf; Vorlagen/Gemini in Slice 1; nur ein Produkt pro Lauf; nur Messung ohne Schätzung

## Slice-2-Delta

| Thema | Entscheidung |
|-------|--------------|
| Nesting | Oberste Ebene = **Produktionslauf** (Hauptname); darunter bis ~10 **Prozesse** (früher Steps) |
| Multi-Link | `production_process_products` + `production_process_families` |
| Kosten | Gleicher Ø-Satz für alle verknüpften Produkte (inkl. Familienmitglieder) |
| Zeiten | `estimated_*_seconds` am Prozess; Messung aus Tracks; Preferenz Messung |
| UI | Inline-Zellen; Produktkosten + Familien-Ø; nach Lauf-Start Fokus auf Prozess-Board (nicht Create-Dead-End); „Aktive Läufe“ immer prominent (`ui-v1.16`) |
