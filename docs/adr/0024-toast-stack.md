# Toast-Stack: bleiben bis Klick, optional Navigation

Hinweise (Erfolg/Warnung/Fehler) erscheinen als **gestapelte Liste** oben rechts mit Zeitstempel. Sie bleiben sichtbar, bis der Nutzer tippt — kein Auto-Dismiss. Liegt ein Navigationsziel vor (`tab` und/oder `run`), fragt der Klick optional **„Zur Stelle?“** und wechselt dann dorthin. Inline-Banner (z. B. Negativbestand auf der Übersicht) nutzen dieselbe Optik, aber ohne feste Overlay-Position, damit sie nicht mit dem Toast-Stack kollidieren.

**Considered Options:** Auto-Dismiss nach wenigen Sekunden (alt); nur Fehler bleiben; Toast schließt und Navigation immer ohne Nachfrage
