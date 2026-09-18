# SQLite NullPool, WAL und Auth-Session-Touch

Production-Hotfix gegen `QueuePool limit of size 5 overflow 10` und intermittierende API-Hangs. SQLite nutzt kein Connection-Pooling (`NullPool`), WAL + `busy_timeout=30s` beim Connect. AuthMiddleware schließt die DB-Session vor `call_next`. Session-Touch schreibt höchstens alle 5 Minuten. IMAP hält keine Session über Netzwerk-I/O und setzt Socket-Timeouts. Neue Mails werden erst nach erfolgreichem DB-Commit nach „verarbeitet“ verschoben (sonst Datenverlust bei Persist-/Parse-Fehler).

**Status:** accepted

**Considered Options:** QueuePool vergrößern; zweiter uvicorn-Worker; PostgreSQL; Session-Touch unverändert lassen
