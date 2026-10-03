# Manuelle Todos anlegen

Nutzer können Todos manuell anlegen (`source=manual`), nicht nur aus Bestell-Sync / Auto-Einkauf / „Auf Liste“. Alle bestehenden Arten: Fertigen, Artikel anlegen, Zusammenstellen, Einkauf. Bestellung und Position sind optional; freies Zusammenstellen speichert `set_variant_id` am Todo.

Pflichtfelder minimal: Art, Titel, Menge (Default 1); Produkt/Material/Variante optional. `_sync_line_todos` und Auto-Erledigung von Einkauf-Todos greifen nur `source=auto`. Rechte: Admin und Mitarbeiter (Todos-Nav + API-Allowlist). Übersicht zeigt alle offenen Werkstatt-Todos. Ohne Aktions-Referenz öffnet Tippen den Bearbeiten-Dialog; Erledigen nur über Button darin.

**Status:** accepted

**Considered Options:** Nur Fertigen; strenge Pflichtfelder je Art; Manuelle bei Sync löschen; Anlegen nur Admin
