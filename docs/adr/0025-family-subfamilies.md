# Familien-Katalog mit einer Unterebene

Material- und Produktfamilien sind eigene **Kataloge** (Tabellen `material_families` / `product_families`). Genau **eine** Ebene: Elternfamilie → Unterfamilie. Am Artikel hängt nur **eine** Referenz (`family_id` auf Eltern *oder* Unterfamilie). Filter auf Elternfamilie zeigt direkte Artikel plus alle Unterfamilien-Artikel. Pflege im Tab **Kataloge**; am Artikel nur Auswahl. Migration: bestehende Freitext-`family`-Werte werden zu Elternfamilien + Verknüpfung. Löschen nur wenn keine Artikel (und bei Eltern: keine Unterfamilien) hängen. Serienanlage: Find-or-create Elternfamilie aus Basisname. Listen: Elternkopf → optional Unterköpfe → Zeilen.

**Status:** accepted

**Considered Options:** Zwei Freitextfelder Eltern+Unter; Slash-String im alten `family`-Feld; ein gemeinsamer Katalog für Material und Produkt; nur inline ohne Katalog-Tab; flache Listengruppierung ohne Nest
