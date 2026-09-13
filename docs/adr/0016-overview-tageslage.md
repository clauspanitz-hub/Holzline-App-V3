# Tageslage auf der Übersicht (Gemini + App-Kennzahlen)

Die Übersicht zeigt unter Bestellungen/Todos eine **Tageslage**: Kennzahlen rechnet die App, Gemini liefert einmal pro Kalendertag Zusammenfassung (inkl. Todo-Produktnamen), Spruch des Tages und 2–3 Schritte „Als Nächstes“ (echte Todos zuerst, sonst motivierende Geschäftsideen nur als Text). Cache + manueller Refresh; ohne Key oder bei Free-Kontingent (ADR `0017`) bleiben die Zahlen / Fallback-Schritte. Motivationsschritte erzeugen keine Todos. Spätere Kennzahlen (Preise/Kosten/Zeiten) erweitern dieselbe Schicht.

**Considered Options:** Gemini liefert auch die Zahlen; Briefing bei jedem Seitenaufruf; Motivationsideen als echte Todos; Tageslage ganz oben
