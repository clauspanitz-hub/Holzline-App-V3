# JSON-Datensicherung Export/Import

Inventardaten (Kataloge, Materialien, Produkte, Bestände, Sets) werden als eine JSON-Datei (`holzlinge-backup` v1) gesichert und wiederhergestellt — nicht Bestellungen, Todos, Shop-Zuordnungen, Tageslage oder Benutzer. Import bietet Ersetzen oder Zusammenführen (Match über Namen/SKU/Handle; Bestände setzen). Bewegungs-Historie optional. Ergänzt Host-Backups der SQLite-Datei, ersetzt sie nicht.

**Status:** accepted

**Considered Options:** Nur SQLite-Datei-Download; nur CSV-Tabellen; Merge über interne IDs
