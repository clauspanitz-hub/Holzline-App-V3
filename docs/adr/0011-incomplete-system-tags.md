# System-Tags für Unvollständigkeit

Unvollständige Stammdatenfelder erzeugen filterbare Katalog-Tags `fehlt Mindestbestand`, `fehlt Stückliste`, `fehlt Einkaufspreis`, `fehlt Verkaufspreis` (automatisch setzen beim Anlegen/wenn das Feld neu unvollständig wird). Der Tag bleibt, bis das Feld vollständig ist oder man ihn bewusst im Tag-Picker abwählt (= ignorieren bis erneut vollständig→unvollständig). Speichern anderer Dialogfelder sendet die Tag-Liste nicht mit und darf `fehlt …` nicht entfernen. Tags sind kataloggeschützt; das Listen-„!“ folgt nur noch gesetzten `fehlt …`-Tags. Einmaliger Backfill beim ersten Anlegen der System-Tags.

**Status:** accepted

**Considered Options:** Nur UI-Hinweis ohne Tags; ein Sammel-Tag `unvollständig`; Sync bei jedem Read; manuelles Entfernen ohne Wirkung (sofort wieder setzen)
