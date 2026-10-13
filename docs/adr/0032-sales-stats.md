# Verkaufsstatistik aus shipped Order-Lines + Opt-in Picker-Ranking

Claus braucht die Häufigkeit verkaufter Lagerprodukte und dieselbe Reihenfolge optional in Auswahl-Listen. Neuer Slice außerhalb Phasen 1–5 (Anti-Scope-Creep); Datenquelle = Phase-2-Bestellungen.

**Status:** accepted (MVP)

**Considered Options:** Persistente Ranking-Tabelle; Rolling-Zeitfenster; Metrik „Anzahl Bestellungen“; Set-Varianten als eigene Ranking-Objekte; Telegram/Push; Shop-Write

## Entscheidung

| Thema | Entscheidung |
|-------|--------------|
| Verkauft | Nur Bestellungen `status == "shipped"` |
| Metrik | Stückzahl (Summe Mengen je Lagerprodukt), Zeitraum Gesamt |
| Sets | Varianten-BOM auflösen; nur BOM-**Produkte** (`qty_line × quantity_required`); BOM-Materialien ignoriert |
| Aggregation | On-read aus `orders` / `order_lines` / `set_bom_lines` — keine neue Persistenz |
| API | `GET /api/stats/product-sales?limit=` (Admin + Mitarbeiter read) |
| UI | Top-10 auf Übersicht + Nav-Seite **Statistik** (volle Liste, nur Mengen > 0) |
| Picker | Opt-in „nach Verkauf sortieren“ an Produkt-`FamilySelect`; Standard aus; Persistenz `localStorage` |
| Sort bei Opt-in | Flache Verkaufsreihenfolge (häufig zuerst); Familie nur als Label |

## Konsequenzen

- Neuer Slice; kein Telegram, Shop-Write, Rolling-Fenster, Order-Count-Metrik
- Material-/Freitext-Positionen erscheinen nicht in der Produktstatistik
- Ranking kann bei vielen Bestellungen später gecacht werden — MVP braucht das nicht
