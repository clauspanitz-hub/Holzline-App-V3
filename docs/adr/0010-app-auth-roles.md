# App-Login mit Rollen Admin und Mitarbeiter

Phase-2-Start: Pflicht-Login per Benutzername/Passwort (Session-Cookie, Idle ~12 h). Erster Admin per ENV (`ADMIN_USER`/`ADMIN_PASSWORD`). Admin verwaltet Benutzer in der UI. Rolle **Mitarbeiter** sieht und nutzt nur **Bei Mitarbeitern** (Umwandeln); API entsprechend gesperrt. Eigenes Passwort änderbar; Admin setzt fremde Passwörter. Caddy nur TLS — keine App-Rechte über Basic-Auth.

**Status:** accepted

**Considered Options:** Nur Caddy Basic-Auth; LAN ohne Login; OAuth/SSO; Rolle Werkstatt mit Schreibrechten auf Material/Produkt
