# Projekt: Holzlinge Inventar- & Materialverwaltung

## 1. Übersicht & Zielsetzung
Eine schlanke, modulare Webanwendung zur Verwaltung von Materialien, Produkten, Standorten und Shopify-Sets für die Holzmanufaktur Holzlinge.
- **Hosting-Ziel:** Proxmox Server (Docker Compose in einem Debian/Ubuntu-LXC).
- **Interface:** Vollständig responsive (Desktop für Planung, Mobile für Übersicht/Nutzung).
- **Fachsprache:** siehe `CONTEXT.md`.

## 2. Tech-Stack
- **Backend:** FastAPI (Python 3.12)
- **Frontend:** Svelte (Vite) – SPA, ausgeliefert über FastAPI
- **Datenbank:** SQLite (Datei im Docker-Volume; NullPool, WAL, busy_timeout — ADR `0022`)
- **ORM:** SQLAlchemy 2.x (Schema-Init/Migration-Hilfen beim Start)
- **Container:** Docker & Docker Compose (ein Service)
- **ADRs:** `docs/adr/`

## 3. Datenmodell

### Phase 1 (Basis)
- **materials:** … optional `min_stock` / `reorder_quantity` / `last_purchase_quantity`, optional `alternatives_note` / `products_note`, Bezugsquellen in `material_purchase_sources` (Shop + URL), …
- **products:** `id`, `name` (unique), `sku` (optional unique), `selling_price` (Verkaufspreis EUR, 0 = unvollständig), optional `min_stock`/`color`/`tags`/`family_id` (Produktfamilien-Katalog, ADR `0025`), `is_template`, Audit wie Materialien — kein Gesamtbestand mehr an der Zeile
- **material_families / product_families:** Kataloge Eltern → eine Unterebene; Artikel referenziert genau einen Knoten (ADR `0025`)
- **Unvollständig (UI):** Material: Mindestbestand, Einkaufspreis=0; Produkt: Mindestbestand, Stückliste, Verkaufspreis=0 — sichtbar als „!“ und als System-Tags `fehlt …` (ADR `0011`)
- **product_materials:** Produkt-Stückliste — Material **oder** Komponenten-Produkt → Fertigen (ADR `0012`)
- **Materialherstellkosten:** live aus Produkt-Stückliste

### Phase 1.5 (Standorte & Sets) — Umgesetzt
- **locations:** Hamburg, Dahlenburg, In Bearbeitung, MA1, MA2, Ausschuss (virtuell)
- **material_stocks / product_stocks:** Bestand je Standort, Negativ erlaubt + Warnung
- **materials / products:** optionales `min_stock` (Mindestbestand) — Übersicht zeigt kritische Artikel (Gesamt ≤ 0 oder unter Mindestbestand)
- **products.transform_target_id:** Legacy-Spalte; Umwandlung Uni→Vintage läuft per Name (ADR `0006`)
- **stock_movements:** Historie für Umbuchungen mit virtuellen Standorten und für Umwandlungen
- **Bei Mitarbeitern:** Überblick Produkte mit Bestand an MA1/MA2; Umwandeln Uni→Vintage per Name
- **sets:** Shopify-Set ohne eigenen Bestand; Flag `count_materials_in_buildability`
- **set_variants:** Option1–3 Name/Value (Shopify-CSV-Assistent: Set / Serie / On-Demand / ignorieren; kein stilles Anlegen aller Varianten als Sets)
- **shopify_ignored_handles:** dauerhaft ignorierte Shopify-Handles im Assistenten
- **shopify_import_queue:** Import-Warteschlange (Serie/On-Demand → Serienanlage); Produkte `is_on_demand`
- **set_bom_lines:** Varianten-Stückliste → Material **oder** Produkt + Menge
- **option_mappings:** Regel Option+Wert → Material/Produkt+Menge; Overrides je Variante möglich
- **Baubare Menge:** `min(floor(sum_stock/qty))` über relevante Zeilen; Summe über Standorte **ohne Ausschuss**

### Phase 2 (Bestellungen & Auth) — umgesetzt
- **users / auth_sessions:** App-Login; Rollen Admin / Mitarbeiter (ADR `0010`)
- **orders:** Herkunft Shopify/Etsy/Manuell; Status **zur Prüfung** (`review`) / **offen** / **versandbereit** / **versendet**; externe Nummer; Kunde; Bestellzeit; optionale **Notiz** (Personalisierung)
- **order_lines:** Menge, Label; optional `product_id`, `material_id`, `set_variant_id` (XOR), `shop_sku`, `shop_title`, `suggested_product_id` (Gemini-Vorschlag)
- **todos:** Arten Artikel anlegen / Fertigen / Zusammenstellen / Einkauf; Einkauf ohne Bestellung möglich; halten Bestellung auf **offen** wenn verknüpft
- **shop_line_maps:** gemerkte Shop-Zuordnung (Herkunft + Titel/SKU → Produkt); Gemini nur Vorschlag (ADR `0014`)
- **tageslage_cache:** ein Eintrag pro Kalendertag (Zusammenfassung, Spruch, Nächste Schritte; ADR `0016`)
- **incoming_mails:** IMAP-Warteschlange (Rohtext; Etsy-Parser → Bestellung zur Prüfung; ADR `0018`)

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
- [x] Familien-Katalog mit Unterfamilien (Material/Produkt getrennt, eine Ebene, ADR `0025`)

### Phase 2: Bestellverwaltung & Eingangskanäle — Umgesetzt
- [x] Benutzer mit Rechten (App-Login Admin/Mitarbeiter, ADR `0010`)
- [x] Manuelle Schnellerfassung + Todo-Liste (Artikel anlegen / Fertigen / Zusammenstellen)
- [x] Shopify-API → Bestellungen (bezahlt, nicht voll erfüllt; Match → offen+Todos, sonst **zur Prüfung**; Abruf nur Knopfdruck; Dev-Dashboard Client-Credentials `SHOPIFY_STORE` / `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET`; Versendet manuell; ADR `0013`)
- [x] Shop-Zuordnung merken + Gemini-Vorschlag nach Abruf (ADR `0014`; `GEMINI_API_KEY` optional; Free + Default `gemini-3.1-flash-lite`, ADR `0017`)
- [x] Prüfung: Produkt erzeugen / Auf Liste; Status an offene Todos; Hinweis (ADR `0015`)
- [x] Übersicht: Tageslage (Kennzahlen + Gemini-Text/Spruch/Nächste Schritte, Tages-Cache; ADR `0016`)
- [x] Etsy-Mail + Gemini (IMAP-Warteschlange, seltener Auto-Fetch, Parse-Knopf; ADR `0018`) → **zur Prüfung**; Etsy-API falls/wenn Freigabe; kein CSV-Bestellexport
- [x] Einkauf-Todos aus Mindestbestand (Knopf + Auto erledigen/neu bei Bestand; ADR `0019`, `0023`)
- [x] Zusammenstellen bei Set-Bestellung (Set-Variante an Position, Todo, Abbuchung; ADR `0020`)

### Phase 3: Optimierung & Einkauf — Umgesetzt
- [x] Einkaufsliste aus fehlenden Materialien (Todo-Art Einkauf; ADR `0019`/`0023`)
- [x] Einkaufsquellen + Alternativen am Material (ADR `0021`)
- [x] Mindestbestand je Material/Produkt → Warnungen in Übersicht (vorgezogen in 1.5)
- [x] Toast-Stack (bis Klick, optional „Zur Stelle?“); Material-Filter Negativbestand (ADR `0024`)

## 5. Geschäftsregeln (gültig)
- Keine Reservierungs-/Verschnittlogik.
- **Auth (Phase 2):** Pflicht-Login; Rollen Admin und Mitarbeiter (ADR `0010`).
- **Shopify-Eingang:** Abruf nur auf Knopfdruck; kein Hintergrund-Poll (ADR `0013`).
- **Gemini:** optional; Free-Tier; Default Flash-Lite; nur Vorschläge, kein Gedächtnis (ADR `0014`, `0017`).
- Sets haben keinen Lagerbestand; Zusammenstellen bei Bestellung = Phase 2 (Bestellungen).
- Fertigen erhöht Produktbestand an einem gewählten Standort, Materialabbuchung an gewähltem/selben Standort (Start: ein Standort pro Buchung).
- Baubare Sets aus Summe der Standorte ohne Ausschuss (ADR `0003`, `0006`).
- Einkauf-Todos (nur Materialien): bei Bestandsänderung erledigen wenn Mindestbestand erfüllt (ohne Ausschuss); bei erneuter Unterschreitung neues offenes Todo (ADR `0023`).
- Umwandlung: Uni→Vintage per Name am selben Standort, ohne Materialabbuchung (ADR `0006`).
- Material ohne Varianten-System; unterschiedliche Ausbeuten nur über Produkt-Stücklisten-Mengen.
