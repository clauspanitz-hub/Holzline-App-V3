# Medium als pflegbarer Katalog

Farben behalten den Datenkern Farbe + Medium. Medium ist nicht mehr festes Enum (Lack/PLA), sondern Katalogtabelle `color_media` mit Seed Lack/PLA; Nutzer können Arten anlegen, umbenennen und (mit Warnung) löschen. Farben referenzieren `medium_id`; Löschen einer Art entfernt deren Farben und setzt `color_id` an Material/Produkt auf null.

**Trade-off:** Mehr Flexibilität und UI-Konsistenz mit Tags/Farben-Katalog; etwas mehr Migrations- und Pflegeaufwand als ein festes Enum.

**Status:** accepted
