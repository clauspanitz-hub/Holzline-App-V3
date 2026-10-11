# Produktions-Tracking (Zeit / Aufwand)

Session-Board für parallele **Produktionsläufe** mit **Prozessen** darunter (voraus/live/nachträglich), getrennten Zeitspuren Arbeitszeit und Maschinenzeit, Multi-Select Produkte **und** Familien am Lauf, Mengen an Lauf und Prozess. Schätzung + Messung je Prozess (Messung bevorzugt für Anzeige/Kosten). Maschinen-Stammdaten (Name, Notiz, Leistung W), Stundensatz-Katalog mit Default am User, globaler Stromtarif. Produktkosten pro Typ: aktuell Ø Zeiten × heutige Tarife; Historie als Snapshot nach Lauf-Abschluss für **alle** verknüpften Produkttypen denselben Satz; Familienansicht filterbar mit Durchschnitt bei abweichenden Preisen. Entkoppelt von Fertigen/Lagerbuchung. Kein Shopify-Write, keine Vorlagen/Gemini, kein Material-/Werkzeug-Verschleiß in Slice 1–2.

**Status:** accepted (Slice 1–2 live; Abgeschlossen-Historie Q23–Q30)

**Considered Options:** Nur Timer ohne Kosten; ein Stundensatz; Timing = Fertigen; Menge nur am Lauf; Vorlagen/Gemini in Slice 1; nur ein Produkt pro Lauf; nur Messung ohne Schätzung; In-Place-Overwrite statt Re-Time; eigene Historie-Seite; Diff/Trend-MVP

## Slice-2-Delta

| Thema | Entscheidung |
|-------|--------------|
| Nesting | Oberste Ebene = **Produktionslauf** (Hauptname); darunter bis ~10 **Prozesse** (früher Steps) |
| Multi-Link | `production_process_products` + `production_process_families` |
| Kosten | Gleicher Ø-Satz für alle verknüpften Produkte (inkl. Familienmitglieder) |
| Zeiten | `estimated_*_seconds` am Prozess; Messung aus Tracks; Preferenz Messung |
| UI | Inline-Zellen; Produktkosten + Familien-Ø; Board-first (Create sekundär); „Aktive Läufe“ immer prominent; Pin-Merge gegen leeres Reload (`ui-v1.17`); Stop/Messung ohne Board-500, Nesting bleibt nach Reload (`ui-v1.18`) |

## Abgeschlossen-Historie (Q23–Q30)

| Thema | Entscheidung |
|-------|--------------|
| Eltern | `production_process_templates` — Prozess-Vorlage gruppiert Historie + Re-Times |
| Lauf | `production_processes.template_id` + optionales `history_note` |
| Erneut timen | Neuer `active`-Lauf, gleiches `template_id`; Quell-Lauf bleibt `done` |
| Archiv | Meta (Titel/Notiz/Links) editierbar; Zeiten + Prozessstruktur → 400 |
| UI | Board-Filter **Abgeschlossen** → Vorlage aufklappen → Lauf-Zeilen; keine eigene Historie-Seite; kein Diff/Trend |
