# Holzlinge Inventar

Fachsprache für die interne Inventar-, Material- und Stücklistenverwaltung der Holzmanufaktur Holzlinge.

## Language

**Material**:
Ein Rohstoff oder Zulieferteil, das auf Lager liegt und in Stücklisten von Produkten verwendet wird. Einkauf: Menge + Preis der Packung; daraus Preis pro Einheit.
_Avoid_: Rohmaterial, Rohstoff, Bestandteil, Komponente

**Einkaufsmenge**:
Die Menge einer Material-Packung beim Einkauf in der Material-Einheit (z. B. 750 ml).
_Avoid_: Packungsgröße als UI-Fremdwort

**Einkaufspreis**:
Der Preis für eine komplette Einkaufsmenge (Packung), nicht der Preis pro Verbrauchseinheit.
_Avoid_: Stückpreis (das ist Preis/Einheit)

**Produkt**:
Ein lagergeführtes Einzelteil der Manufaktur (z. B. Ring in einer Farbe, Kerze, Zahlenstecker), mit eigenem Bestand.
_Avoid_: Fertigerzeugnis als Shopify-Set, Artikel (außer als SKU-Synonym), Ware, Variante (als Lagerobjekt)

**Set**:
Eine nur in Shopify (o. ä.) verkaufte Zusammenstellung aus Produkten; hat selbst keinen Lagerbestand und wird bei Bestellung aus vorhandenen Produkten zusammengestellt.
_Avoid_: Produkt (für Sets), Bundle als Lagerartikel, fertiges Set auf Lager

**Variante**:
Eine konkrete Set-Konfiguration in Shopify (z. B. Ringfarbe × Kerzenfarbe × Zahlenfarbe), abbildbar als Stückliste aus Produkten.
_Avoid_: Lager-SKU für das Set selbst

**Stückliste**:
Die Zuordnung, welche Positionen in welcher Menge für eine Einheit benötigt werden. Produkt-Stückliste: Materialien fürs Fertigen. Set-/Varianten-Stückliste: Materialien und/oder Produkte zum Zusammenstellen.
_Avoid_: Recipe, BOM, Rezept, Bill of Materials (in der UI)

**Fertigen**:
Der Vorgang, bei dem eine Menge eines Produkts hergestellt wird: Produktbestand steigt, Materialbestände werden laut Stückliste abgebucht.
_Avoid_: Produzieren, Herstellen, Buchen (als alleiniger Begriff für diesen Vorgang); Zusammenstellen eines Sets (das ist kein Fertigen auf Set-Ebene)

**Zusammenstellen**:
Bei Bestellung eines Sets die benötigten Produkte laut Varianten-Stückliste vom Lager abbuchen (ohne Set-Bestand zu erhöhen).
_Avoid_: Fertigen (für Sets), Kommissionieren als alleiniger UI-Begriff (optional synononym)

**Materialherstellkosten**:
Die Summe der Materialkosten pro Produkteinheit laut Stückliste (Menge × Einkaufspreis je Material).
_Avoid_: Selbstkosten, Verkaufspreis, Deckungsbeitrag

**Einheit**:
Die Maßeinheit eines Materials aus einer festen, im Code gepflegten Liste (Stk, m, kg, g, m², l, ml).
_Avoid_: Freitext-Einheit, Unit als UI-Begriff

**Standort**:
Ein Ort, an dem Material- oder Produktbestand liegt. Physisch: Hamburg, Dahlenburg; virtuell: In Bearbeitung, MA1, MA2 (bei Mitarbeitern), Ausschuss (verworfen). Material-UI zeigt nur die physischen Standorte (+ Gesamt); Produkte alle Standorte inkl. virtueller.
_Avoid_: Location als UI-Begriff, Bin, Am Waldpark 27 / Werkstatt Rissen / Lager Petra (Shopify-Namen, nicht kanonisch)

**Mindestbestand**:
Optionale Untergrenze je Material oder Produkt. Unterschreitung (oder Gesamt ≤ 0 / negativ) markiert den Artikel in der Übersicht als kritisch. Todos/Einkaufsliste daraus = spätere Phase.
_Avoid_: Sollbestand als Pflichtfeld

**Baubare Variante**:
Eine Set-Variante, deren zusammenstellbare Stückzahl sich aus dem über alle Standorte summierten Bestand der Stücklistenzeilen ergibt (`Minimum` über `floor(Bestand/Menge)`). Ob Material-Zeilen mitzählen, ist je Set einstellbar.
_Avoid_: Verfügbarer Set-Bestand (Sets haben keinen Bestand)

**Tag**:
Ein Label zur Gruppierung und Filterung von Materialien und Produkten (mehrere möglich). Einträge kommen aus einem pflegbaren Tag-Katalog; Zuordnung am Artikel. Unabhängig von Farbe/Medium (Art/Option).
_Avoid_: Kategorie als einziges Pflichtfeld; Farboption als Tag

**Farbe**:
Ein benannter Farbeintrag im Katalog (z. B. Rot, Salbeigrün), jeweils mit einem Medium. Material und Produkt können je eine Farbe haben. In der UI: Medium zuerst, dann Farbe/Option.
_Avoid_: Farb-Tag statt Katalogeintrag; „Variante“ oder „Art“ für Farboptionen (Variante = Set; Art nicht mehr als UI-Alias)

**Medium** (Farbe):
Die Art der Farbgebung aus einem pflegbaren Katalog (Start: Lack, PLA). Am Artikel und in Katalogen erscheint **Medium** oberhalb der Farbe; im Katalog je Medium eine eigene Farb-Tabelle. Vorschläge und Matching nur innerhalb desselben Mediums. Katalog-Bereich: **Medien**.
_Avoid_: Materialart, Farbtyp; UI-Label „Art“ (veraltet); „Art“ als eigenes Domänenobjekt neben Medium

**Vorlage** (Produkt):
Ein Produkt, das als Muster für die Serienanlage dient (Stückliste/Tags), markiert durch ein explizites Flag „Ist Vorlage“. Die Serienanlage kopiert davon und setzt je gewählter Farbe ein neues Produkt.
_Avoid_: Template als UI-Fremdwort; nur „ohne Farbe“ als implizite Vorlage

**Serienanlage** (aus Farben):
Auf Knopfdruck Materialien oder Produkte aus gewählten Katalogfarben erzeugen (Auswahl + gemeinsame Defaults). Serien-Materialname = Medium + Farbe; manuell angelegte Materialien frei benennbar. Produktname = Basis + Farbe. Produkt-Serienanlage nutzt optional eine **Vorlage**. Materialien: bereits belegte Farben (gleicher color_id) sind nicht wählbar. Produkte: „schon vorhanden“ gilt für den konkreten Namen Basis+Farbe, nicht für die Farbe allein. Katalog-Umbenennung (Medium/Farbe) benennt Artikel um, die noch den alten Seriennamen tragen.
_Avoid_: Automatisches Anlegen ohne Nachfrage; Serien-Material nur Farbname

**Umwandlung**:
Der Bestandstausch von einem **Quellprodukt** zu einem fest verknüpften **Zielprodukt** am selben Standort (z. B. Uni-Geburtstagsring → Vintage-Geburtstagsring nach Bemalen). Kein Fertigen und kein Umbuchen. Die Umwandlung wird nur angeboten, wenn der Produktname „Uni“ enthält (Groß-/Kleinschreibung egal); die Farbe bleibt die des Quellprodukts.
_Avoid_: Umbuchen für Produktwechsel; Tag als Status „wird Vintage“; stillschweigende Hintergrund-Umbuchung als Ersatz; Umwandeln ohne „Uni“ im Namen

**Quellprodukt / Zielprodukt**:
Feste Produkt-Verknüpfung „wird zu“ / „entsteht aus“ für die Umwandlung. Ein Quellprodukt zeigt auf genau ein Zielprodukt. Typisch: Name mit „Uni“ → Ziel mit Vintage, gleiche Farbe.
_Avoid_: Paarung nur über Namensähnlichkeit ohne Verknüpfung; Uni/Vintage als Zustand desselben Produkts

**Ausschuss** (Standort):
Virtueller Standort für verworfenen Produktbestand (nicht mehr Uni, nicht Vintage). Bestand liegt dort weiter und ist nachvollziehbar; er ist kein verkaufbarer Lagerort. Zählt in der Produkt-Gesamtmenge mit, aber nicht als verfügbarer/baubarer Bestand.
_Avoid_: Stilles Löschen ohne Spur; Tag „Ausschuss“ statt Standort; Ausschuss als Zustand am Produkt

**Bei Mitarbeitern** (Überblick):
Eigene Ansicht für Bestand von Quellprodukten (mit „Wird zu“) an MA1/MA2, inkl. Zugang zur Bewegungshistorie. Unabhängig davon, ob „Uni“ im Namen steht. Kein Ersatz für die normale Produktliste. Der Knopf Umwandeln erscheint nur, wenn der Name „Uni“ enthält.
_Avoid_: Nur Tabellenfilter statt eigener Überblick; Tags als alleinige „bei MA“-Anzeige

**Bewegung** (Bestand):
Eine nachvollziehbare Umbuchung oder Umwandlung, relevant vor allem mit virtuellen Standorten (MA1, MA2, In Bearbeitung, Ausschuss) und für Umwandlungen — Grundlage für den Überblick „wer hat was / was wurde daraus“.
_Avoid_: Tag-Historie; implizite Umbuchung ohne Eintrag

