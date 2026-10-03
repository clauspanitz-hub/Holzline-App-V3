# Einkaufsassistent (Stückpreis aus Einkaufsausbeute)

Seite unter Lager: für alle Materialien Einkaufspreis einer Einkaufseinheit und Ausbeute N je Produkt erfassen. Stückpreis = Preis ÷ N. Übernehmen setzt `purchase_price` (und `purchase_quantity` = 1), BOM-Menge `1/N` und speichert Ausbeuten in `material_product_yields`. Scratch-Modus rechnet ohne DB-Write; mit Name wird beim Übernehmen ein Material angelegt. Kein Shopify-Write.

**Status:** accepted

**Considered Options:** Nur Leimholz/Platten; Ausbeute nur in Freitext; Stückpreis als eigenes Produktfeld; mehrere Materialien in einem Durchgang
