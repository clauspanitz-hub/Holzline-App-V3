# Materialbedarf-Export PDF/CSV (Lieferantenbestellungen)

Offene Einkauf-Todos (auto und manuell) bilden die Materialbedarfsliste. Export als **CSV** (Semikolon, UTF-8-BOM, Excel DE) und **PDF** (Querformat, DejaVu) unter Todos: **Bedarf CSV** / **Bedarf PDF**. Spalten u. a. Material, Menge, Einheit, verfügbarer Bestand, Mindestbestand, bevorzugte Bezugsquelle (Shop + URL). Kein Shopify-Write, kein Telegram, kein Barcode. Endpunkte `GET /api/todos/purchase-export.csv|.pdf` — Admin und Mitarbeiter.

**Status:** accepted

**Considered Options:** Nur kritische Materialien ohne Todos; nur CSV; BOM-Bedarf aus offenen Fertigen-Todos; Browser-Print statt Server-PDF
