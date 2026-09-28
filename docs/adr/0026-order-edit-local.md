# Bestellungen lokal bearbeiten (Positionen + Notiz)

Admin kann Bestellungen in Status **offen**, **zur Prüfung** oder **versandbereit** bearbeiten: Positionen hinzufügen/entfernen, Menge ändern, optionale Notiz. **Versendet** ist gesperrt. Änderungen betreffen nur die App-Datenbank — **kein** Schreiben nach Shopify oder Etsy (ADR `0013` bleibt Read-only für den Shop-Abruf).

Bei Positionsänderungen werden Werkstatt-Todos neu synchronisiert (`_sync_line_todos`): entfernte Positionen verlieren offene Todos (Cascade/Löschen); neue oder geänderte Mengen erzeugen passende Todos. In Status **zur Prüfung** bleiben Fertigen-/Zusammenstellen-Todos aus (wie bei Zuordnung); Abnicken erzeugt sie weiterhin. Leere Positionsliste ist erlaubt (Warnung in `notices`); die Bestellung bleibt bestehen.

UI: Dialog/Sheet an der Bestellung (Buttons, kein Inline-Zellen-Edit), Muster wie UI-Redesign (Aktionskarten/Modals). Neue Position: Katalog-Produkt/Material/Set-Variante oder Freitext.

**Considered Options:** Inline-Tabellen-Edit; Zurückschreiben nach Shopify; Nur offene Status; Leere Bestellung blockieren
