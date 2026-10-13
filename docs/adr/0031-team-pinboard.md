# Team-Pinnwand + Scratchpad in der App-Shell

Zwei Personen (Claus/Simona) brauchen zeitgestempelte Hinweise und ein gemeinsames Notizfeld ohne Chat-Komplexität. Neuer Slice außerhalb Phasen 1–5 (Anti-Scope-Creep).

**Status:** accepted (MVP)

**Considered Options:** Login-User als Absender; Threads/Objekt-Kommentare; Ungelesen/Push/Telegram; eigene Seite statt Shell-Rail; WebSocket-Realtime

## Entscheidung

| Thema | Entscheidung |
|-------|--------------|
| Form | Flache `team_messages` (Text + Zeitstempel + Absender); CRUD inkl. Bearbeiten/Löschen |
| Absender | UI-Schalter **Claus \| Simona** — nicht der Session-User |
| Notizen | Singleton `team_notes` (id=1), gemeinsames Scratchpad |
| Desktop | Persistente **rechte Rail** in der App-Shell (überall eingeloggt); Nachrichten oben, Notiz unten |
| Mobile | Button → Sheet/Vollbild mit derselben UI |
| Auth | App-Login Voraussetzung für Shell; Admin + Mitarbeiter (Allowlist) |
| Realtime | Kein WebSocket; Reload/Refresh nach Aktion |

## Konsequenzen

- Neuer Slice; kein Ungelesen, Push, Telegram, Threads im MVP
- Absender ≠ Session-User (bewusst)
- Tabellen per `create_all` + Seed der Notiz-Zeile
