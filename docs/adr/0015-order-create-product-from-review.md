# Produkt aus Bestellprüfung anlegen, Status an Todos binden

Fehlende Shop-Artikel werden in der Prüfung per Button **Produkt erzeugen** (Dialog mit Shop-Daten vorausgefüllt) oder **Auf Liste** (Todo **Artikel anlegen**, sofort sichtbar) behandelt — nicht still und nicht über die CSV-Import-Warteschlange. Speichern verknüpft die Zeile, merkt die Shop-Zuordnung und erledigt das Todo; aus diesem Weg nur Produkte. **Abnicken** bleibt die Freigabe nach **offen**. Offene Todos setzen den Status auf **offen** (Query, nicht nur ORM-Collection); **versandbereit** nur ohne offene Todos, mit kurzem Hinweis an der Bestellung. Layout der Prüfung bleibt für einen späteren UI-Neubau.

**Considered Options:** Import-Warteschlange für Bestellzeilen; versandbereit mit Warnung statt Status-Fix; Abnicken entfällt wenn alles zugeordnet
