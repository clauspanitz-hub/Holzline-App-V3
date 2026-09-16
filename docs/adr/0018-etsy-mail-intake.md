# Etsy-Bestelleingang über IMAP-Warteschlange und Gemini

Etsy-API/CSV fehlen noch; Brücke ist ein **eigenes Postfach** (Weiterleitung). Die App holt Mails per **IMAP** selten automatisch (ca. 2–4×/Tag) und speichert den Text in einer Warteschlange; im Postfach nach Ordner **verarbeitet**. Der Admin-Knopf prüft zuerst auf neue Mails, parst dann alle Wartenden mit Gemini (Nummer + ≥1 Position; Kunde optional) → immer **zur Prüfung**, danach Produkt-Vorschläge wie nach Shopify-Abruf. Doppel (gleiche Etsy-Nummer): Hinweis, nur Ignorieren; Teilfehler blockieren keine Erfolge. Secrets nur ENV. Schnellerfassung bleibt, UI zugeklappt. Später erweiterbar um andere Mail-Arten (Einkauf/Todos).

**Considered Options:** Nur Knopf ohne Auto-Fetch; Gemini bei jedem Poll; Mail-Text erst beim Parsen holen; Doppel still überspringen wie Shopify; Postfach-Passwort in der UI
