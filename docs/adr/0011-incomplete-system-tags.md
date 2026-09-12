# System-Tags für Unvollständigkeit

Unvollständige Stammdatenfelder erzeugen filterbare Katalog-Tags `fehlt Mindestbestand`, `fehlt Stückliste`, `fehlt Einkaufspreis`, `fehlt Verkaufspreis` (automatisch setzen beim Speichern; manuell entfernen = ignorieren bis erneut vollständig→unvollständig). Tags sind kataloggeschützt; das Listen-„!“ folgt nur noch gesetzten `fehlt …`-Tags. Einmaliger Backfill beim ersten Anlegen der System-Tags.

**Status:** accepted

**Considered Options:** Nur UI-Hinweis ohne Tags; ein Sammel-Tag `unvollständig`; Sync bei jedem Read; manuelles Entfernen ohne Wirkung (sofort wieder setzen)
