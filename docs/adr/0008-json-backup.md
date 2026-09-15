# JSON-Datensicherung Export/Import

Inventardaten werden als eine JSON-Datei (`holzlinge-backup` v1) gesichert und wiederhergestellt. Import bietet Ersetzen oder Zusammenführen (Match über Namen/SKU/Handle; Bestände setzen). Bewegungs-Historie optional. Bestellungen/Todos sind nicht im Format — **Ersetzen** leert sie mit, sonst blieben sie nach dem Produkt-Wipe ohne Zuordnung (Shopify-Nummern würden nicht neu eingelesen). Ergänzt Host-Backups der SQLite-Datei, ersetzt sie nicht.

**Status:** accepted

**Considered Options:** Nur SQLite-Datei-Download; nur CSV-Tabellen; Merge über interne IDs
