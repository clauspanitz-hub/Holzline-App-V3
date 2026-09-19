# Einkauf-Todos auto erledigen und neu anlegen

Offene Einkauf-Todos werden **erledigt** (nicht gelöscht), sobald der verfügbare Bestand (Summe Standorte **ohne Ausschuss**) den Mindestbestand erfüllt bzw. das Material nicht mehr kritisch ist. Sinkt der Bestand später wieder unter den Mindestbestand (oder ≤ 0), legt die App **sofort automatisch** ein **neues** offenes Einkauf-Todo an; das alte bleibt erledigt. Höchstens **eines offen** pro Material. Trigger: jede Material-Bestandsänderung (Korrektur, Delta/Einkaufsbuchung, Umbuchen, Fertigen, Zusammenstellen). Nachzieh-Hilfe: Knopf **Einkauf-Todos erzeugen**. Beim Öffnen der Todo-Liste nur veraltete erledigen. Ignorierte Kritische: Auto-Anlegen überspringt sie (Knopf fragt weiter nach). Erweitert ADR `0019`.

**Status:** accepted

**Considered Options:** Todos löschen statt erledigen; nur Knopf ohne Auto-Anlegen; Auto auch für Produkte; Fehlmenge als Todo-Menge
