# Projekt: Holzlinge Inventar- & Materialverwaltung

## 1. Übersicht & Zielsetzung
Eine schlanke, modulare Webanwendung zur Verwaltung von Materialien, Produkten, Standorten und Shopify-Sets für die Holzmanufaktur Holzlinge.
- **Hosting-Ziel:** Proxmox Server (Docker Compose in einem Debian/Ubuntu-LXC).
- **Interface:** Vollständig responsive (Desktop für Planung, Mobile für Übersicht/Nutzung).
- **Fachsprache:** siehe `CONTEXT.md`.

## 2. Tech-Stack
- **Backend:** FastAPI (Python 3.12)
- **Frontend:** Svelte (Vite) – SPA, ausgeliefert über FastAPI
- **Datenbank:** SQLite (Datei im Docker-Volume)
- **ORM:** SQLAlchemy 2.x (Schema-Init/Migration-Hilfen beim Start)
- **Container:** Docker & Docker Compose (ein Service)
- **ADRs:** `docs/adr/`

## 3. Datenmodell

### Phase 1 (Basis)
- **materials:** `id`, `name` (unique), `unit`, `purchase_quantity`, `purchase_price`, `cost_per_unit` (= Preis/Einkaufsmenge), optional `min_stock`/`color`/`tags`/`family` (Materialfamilie), `is_template`, Audit `created_at`/`updated_at`/`created_by`/`updated_by` — Bestand nur in `material_stocks`
- **products:** `id`, `name` (unique), `sku` (optional unique), `selling_price` (Verkaufspreis EUR, 0 = unvollständig), optional `min_stock`/`color`/`tags`/`family` (Produktfamilie), `is_template`, Audit wie Materialien — kein Gesamtbestand mehr an der Zeile
- **Unvollständig (UI):** Material: Mindestbestand, Einkaufspreis=0; Produkt: Mindestbestand, Stückliste, Verkaufspreis=0 — sichtbar als „!“ und als System-Tags `fehlt …` (ADR `0011`)
- **product_materials:** Produkt-Stückliste — Material **oder** Komponenten-Produkt → Fertigen (ADR `0012`)
- **Materialherstellkosten:** live aus Produkt-Stückliste

### Phase 1.5 (Standorte & Sets) — AKTUELL
- **locations:** Hamburg, Dahlenburg, In Bearbeitung, MA1, MA2, Ausschuss (virtuell)
- **material_stocks / product_stocks:** Bestand je Standort, Negativ erlaubt + Warnung
- **materials / products:** optionales `min_stock` (Mindestbestand) — Übersicht zeigt kritische Artikel (Gesamt ≤ 0 oder unter Mindestbestand)
- **products.transform_target_id:** feste Verknüpfung Quellprodukt → Zielprodukt für **Umwandlung** (ADR `0006`)
- **stock_movements:** Historie für Umbuchungen mit virtuellen Standorten und für Umwandlungen
- **Bei Mitarbeitern:** Überblick Quellprodukte mit Bestand an MA1/MA2
- **sets:** Shopify-Set ohne eigenen Bestand; Flag `count_materials_in_buildability`
- **set_variants:** Option1–3 Name/Value (Shopify-CSV-Assistent: Set / Serie / On-Demand / ignorieren; kein stilles Anlegen aller Varianten als Sets)
- **shopify_ignored_handles:** dauerhaft ignorierte Shopify-Handles im Assistenten
- **shopify_import_queue:** Import-Warteschlange (Serie/On-Demand → Serienanlage); Produkte `is_on_demand`
- **orders / order_lines / todos:** manuelle Bestellung → Werkstatt-Todos (Artikel anlegen / Fertigen); Status offen / versandbereit / versendet
- **set_bom_lines:** Varianten-Stückliste → Material **oder** Produkt + Menge
- **option_mappings:** Regel Option+Wert → Material/Produkt+Menge; Overrides je Variante möglich
- **Baubare Menge:** `min(floor(sum_stock/qty))` über relevante Zeilen; Summe über Standorte **ohne Ausschuss**

**Einheiten:** `Stk`, `m`, `kg`, `g`, `m²`, `l`, `ml`

## 4. Phasen-Roadmap

### Phase 1: MVP Inventar & Stücklisten — Umgesetzt
- [x] CRUD Material/Produkt, Stückliste, Fertigen, Docker, UI

### Phase 1.5: Standorte, Sets, Baubarkeit — Umgesetzt (Kern)
- [x] Standorte + Bestände je Standort + Umbuchen
- [x] Sets / Varianten (CSV-Import Struktur)
- [x] Options-Mapping + Varianten-Stückliste (Material und/oder Produkt)
- [x] Übersicht baubare Varianten
- [x] Fertigen/Korrekturen standortbezogen
- [x] Tags + Farben (Medium Lack/PLA), Filter, Vorschläge Stückliste/Sets (ADR `0004`)
- [x] Medium als Katalog; Katalog-Tab; Serienanlage Materialien/Produkte aus Farben
- [x] Medium als Katalog (Art), Farben/Optionen, Tags-Katalog, Tab Kataloge (ADR `0005`)
- [x] Produkt-Flag „Ist Vorlage“ + Serienanlage-UX (Vorlagen priorisiert)
- [x] Material-Flag „Ist Vorlage“ + Serienanlage wie Produkte (Stammdaten/Tags; Familie aus Vorlage bzw. Medium)
- [x] Standort Ausschuss; Quell→Ziel; Umwandeln; Bewegungs-Historie; Bei Mitarbeitern (ADR `0006`)
- [x] Serien-Mindestbestand; Produktfamilie; Mehrfachbearbeitung (ADR `0007`)
- [x] JSON-Datensicherung Export/Import; Übersicht mit Familienfilter; leichtes UI-Split (ADR `0008`)
- [x] Materialfamilie; Übersicht Produkte zuerst + Ignorieren; Set-Zuordnung über Katalogfarbe (ADR `0009`)
- [x] Unvollständigkeit → System-Tags `fehlt …` + „!“ nur bei gesetztem Tag (ADR `0011`)
- [x] Produkt-Stückliste Material oder Komponenten-Produkt; Fertigen/Kosten/Serie (ADR `0012`)
- [x] Shopify-CSV-Assistent + Ignorieren-Liste; Import-Warteschlange → Serienanlage (Medium/Farb-Match); `is_on_demand`

### Phase 2: Bestellverwaltung & Eingangskanäle — in Arbeit
- [x] Benutzer mit Rechten (App-Login Admin/Mitarbeiter, ADR `0010`) — Teilumsetzung Auth
- [x] Manuelle Schnellerfassung + Todo-Liste (Artikel anlegen / Fertigen; kein Set-Zusammenstellen in diesem Schnitt)
- [x] Shopify-API → Bestellungen (bezahlt, nicht voll erfüllt; Match → offen+Todos, sonst **zur Prüfung**; Polling; Token `SHOPIFY_STORE` / `SHOPIFY_ADMIN_TOKEN`; Versendet manuell)
- [ ] Etsy-Mail + Gemini (Hintergrund) → dieselben Bestellungen **zur Prüfung**; Etsy-API falls/wenn Freigabe; kein CSV-Bestellexport
- [ ] Zusammenstellen bei Set-Bestellung (nach hinten)
- [ ] Einkauf-Todos aus Mindestbestand (Liste/Filter schon vorbereitet)

### Phase 3: Optimierung & Einkauf (GEPLANT — vorgemerkt aus Grill)
- [ ] Einkaufsliste aus fehlenden Materialien (Todo-Art Einkauf)
- [ ] Einkaufsquellen + Alternativen am Material
- [x] Mindestbestand je Material/Produkt → Warnungen in Übersicht (vorgezogen in 1.5)

## 5. Geschäftsregeln (gültig)
- Keine Reservierungs-/Verschnittlogik.
- **Auth (Phase 2):** Pflicht-Login; Rollen Admin und Mitarbeiter (ADR `0010`).
- Sets haben keinen Lagerbestand; Zusammenstellen bei Bestellung = Phase 2 (Bestellungen).
- Fertigen erhöht Produktbestand an einem gewählten Standort, Materialabbuchung an gewähltem/selben Standort (Start: ein Standort pro Buchung).
- Baubare Sets aus Summe der Standorte ohne Ausschuss (ADR `0003`, `0006`).
- Umwandlung: Bestand Quellprodukt → Zielprodukt am selben Standort, ohne Materialabbuchung (ADR `0006`).
- Material ohne Varianten-System; unterschiedliche Ausbeuten nur über Produkt-Stücklisten-Mengen.
