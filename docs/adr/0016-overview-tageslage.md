# Tageslage auf der Übersicht (Gemini + App-Kennzahlen)

Die Übersicht zeigt unter Bestellungen/Todos eine **Tageslage**: Kennzahlen rechnet die App, Gemini liefert einmal pro Kalendertag Zusammenfassung (inkl. Todo-Produktnamen), Spruch des Tages und 2–3 Schritte „Als Nächstes“ (echte Todos zuerst, sonst motivierende Geschäftsideen nur als Text). Cache + manueller Refresh (Force überschreibt auch fehlerhaften Tages-Cache). Ohne Key, bei Free-Kontingent/404 oder API-Fehler (ADR `0017`): Kennzahlen bleiben; „Als Nächstes“ aus offenen Todos; fester Hinweis-/Fallback-Spruch. Motivationsschritte erzeugen keine Todos. Spätere Kennzahlen (Preise/Kosten/Zeiten) erweitern dieselbe Schicht.

**Considered Options:** Gemini liefert auch die Zahlen; Briefing bei jedem Seitenaufruf; Motivationsideen als echte Todos; Tageslage ganz oben
