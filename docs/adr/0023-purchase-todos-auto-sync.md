# Einkauf-Todos auto erledigen und neu anlegen

Offene Einkauf-Todos werden **erledigt** (nicht gelöscht), sobald kein Einkauf mehr nötig ist: verfügbarer Bestand (Summe Standorte **ohne Ausschuss**) erfüllt den Mindestbestand bzw. ist nicht mehr kritisch **und** kein Standort (ohne Ausschuss) ist negativ. Sinkt der Bestand unter den Mindestbestand, auf ≤ 0, oder wird ein Standort negativ (typisch nach Fertigen/Zusammenstellen), legt die App **sofort automatisch** ein **neues** offenes Einkauf-Todo an; das alte bleibt erledigt. Höchstens **eines offen** pro Material. Nur **Materialien** — Produkte bekommen keine Einkauf-Todos (Fertigen). Trigger: jede Material-Bestandsänderung (Korrektur, Delta/Einkaufsbuchung, Umbuchen, Fertigen, Zusammenstellen). Nachzieh-Hilfe: Knopf **Einkauf-Todos erzeugen**. Beim Öffnen der Todo-Liste nur veraltete erledigen. Ignorierte Kritische: Auto-Anlegen überspringt sie (Knopf fragt weiter nach). Erweitert ADR `0019`; schließt ROADMAP „Negativbestand nach Fertigung“ (ADR `0002`).

**Status:** accepted

**Considered Options:** Todos löschen statt erledigen; nur Knopf ohne Auto-Anlegen; Auto auch für Produkte; Fehlmenge als Todo-Menge; nur Gesamt ≤ 0 ohne Standort-Negativ
