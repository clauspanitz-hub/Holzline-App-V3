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

**Options-Zuordnung** (Set):
Verknüpfung Shopify-Option → Lagerinhalt. Pro Options-**Name**: **Medium**, **Vorlage/Familie** (bzw. Basis), **Artikel-Typ** (Produkt oder Material). Menge in der Options-Zuordnung immer **1**. Shopify-**Werte**-Liste: Katalogfarbe matchen (Name, Aliase wie pink→Rosa / weiß→Weiss, Dunkel/Hell-Umordnung z. B. Dunkelblau→BlauDunkel); bei 0/mehreren Treffern Zeile markieren und **Dropdown mit Kandidaten** (+ überspringen). Artikel bevorzugt über **Vorlagen-Serie** (Vorlagenname ohne Farbe, z. B. „Geburtstagsring - Uni“), sonst Familie/Basisname + Farbe; fehlt → nachlegen. Typische Ketten: Ringfarbe→Ring-Produkt (Lack); Kerzenfarbe→Kerzenset-Produkt; Zahlenfarbe→Ziffernset-Produkt (PLA).
_Avoid_: Menge ≠ 1 in der Options-Zuordnung; stilles Matchen bei Mehrdeutigkeit; Extra-Modal als einzige Klärung; Zahlen-/Kerzenfarbe → Einzelteile statt Set-Produkt; Familie allein wählen wenn Vorlage Uni/Vintage trennt

**Kerze / Kerzenset**:
Einzelkerzen sind **Material**. Ein **Kerzenset** (z. B. 10 kleine Kerzen + 1 Lebenslicht) ist ein **Produkt** mit Stückliste aus diesen Materialien. Die Shopify-Option **Kerzenfarbe** zeigt in der Options-Zuordnung auf das **Kerzenset-Produkt** der jeweiligen Farbe (nicht auf die Einzelkerze).
_Avoid_: Kerzenfarbe → Einzelkerzen-Material als Normalfall im Geburtstagsring-Set; Kerzenset ohne Stückliste

**Ziffer / Ziffernset**:
Einzelne Ziffern sind **Produkte**. Kanonischer Name: `Ziffern Einzeln - {0–9} - {Farbe}` (Medium **PLA** steckt in der Farbe, nicht im Namen). Alle Einzelziffern gehören zur Produktfamilie **`Ziffern`**. Ein **Ziffernset** (typisch 11 Ziffern: 0–9 plus ggf. Extra) ist ebenfalls ein **Produkt** mit Stückliste aus diesen Ziffern-Produkten, farbgebunden über Medium **PLA**. Die Shopify-Option **Zahlenfarbe** (o. ä.) zeigt in der Options-Zuordnung auf das **Ziffernset-Produkt** der jeweiligen Farbe — dieses wird dem Ring-Set zugeordnet, nicht die Einzelziffern.
_Avoid_: Zahlenfarbe → einzelne Ziffern als Normalfall in der Set-Zuordnung; Einzelziffern als Material; Name ohne zweiten Bindestrich vor der Farbe (`… - 1 Beige`); Familie pro Ziffer statt `Ziffern`

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
Ein Label zur Gruppierung und Filterung von Materialien und Produkten (mehrere möglich). Einträge kommen aus einem pflegbaren Tag-Katalog; Zuordnung am Artikel. Unabhängig von Farbe/Medium (Art/Option). Beim Setzen an einem Artikel Nachfrage: Tag auch der **gleichen Produkt- bzw. Materialfamilie** geben? Auswahl-UI analog Medium/Farbe (Serienanlage): bereits vorhandene/zutreffende Tags **ausgegraut**.
_Avoid_: Kategorie als einziges Pflichtfeld; Farboption als Tag; stilles Taggen aller Artikel ohne Nachfrage (außer System-Tags für Unvollständigkeit); „alle“ = gesamte Produkt-/Materialliste ohne Familienbezug

**Unvollständigkeit** (Stammdaten):
Fehlende Pflicht-Infos an Material oder Produkt: Material **Mindestbestand** / **Einkaufspreis** (=0); Produkt **Mindestbestand** / **Stückliste**. Die App setzt dazu automatisch die System-Tags `fehlt Mindestbestand`, `fehlt Stückliste`, `fehlt Einkaufspreis` (kataloggeschützt). Manuelles Entfernen eines solchen Tags = diese Warnung ignorieren, bis das Feld wieder vollständig und danach erneut unvollständig wird. Das rote „!“ in der Liste zeigt nur Felder, deren `fehlt …`-Tag noch gesetzt ist.
_Avoid_: Unvollständigkeit nur als unsichtbare Berechnung ohne Filter; Katalog-Umbenennen/Löschen der `fehlt …`-Tags; Familien-Propagierung für System-Tags

**Farbe**:
Ein benannter Farbeintrag im Katalog (z. B. Rot, Salbeigrün), jeweils mit einem Medium. Material und Produkt können je eine Farbe haben. In der UI: Medium zuerst, dann Farbe/Option.
_Avoid_: Farb-Tag statt Katalogeintrag; „Variante“ oder „Art“ für Farboptionen (Variante = Set; Art nicht mehr als UI-Alias)

**Medium** (Farbe):
Die Art der Farbgebung aus einem pflegbaren Katalog (Start: Lack, PLA). Am Artikel und in Katalogen erscheint **Medium** oberhalb der Farbe; im Katalog je Medium eine eigene Farb-Tabelle. Vorschläge und Matching nur innerhalb desselben Mediums. Katalog-Bereich: **Medien**.
_Avoid_: Materialart, Farbtyp; UI-Label „Art“ (veraltet); „Art“ als eigenes Domänenobjekt neben Medium

**Mehrfachbearbeitung**:
Gleichzeitiges Setzen ausgewählter Felder für mehrere Materialien oder Produkte. Erlaubt ohne Extra-Warnung: Mindestbestand, Tags; bei Produkten zusätzlich Produktfamilie und Ist-Vorlage; bei Materialien zusätzlich Materialfamilie. Mit **warnender Nachfrage** vor dem Speichern außerdem: **Bestand** (gleicher Absolutwert an einem gewählten Standort — typisch zum initialen Bereinigen der kritischen Liste) und **Stückliste** (eine Zeile hinzufügen oder ändern; übrige Zeilen bleiben). Nicht per Mehrfach: Name, Farbe. Auswahl: Checkboxen in der Tabelle und/oder „ganze Produkt-/Materialfamilie“.
_Avoid_: Massen-Umbenennung; Massen-Farbänderung; Bestand/Stückliste ohne Warn-Dialog; Mehrfach-Bestand als Delta; Mehrfach-Stückliste als komplettes Ersetzen aller Zeilen

**Produktfamilie**:
Optionale Bezeichnung, unter der zusammengehörige Produkte gruppiert werden (z. B. alle Einzelziffern unter **`Ziffern`**). Bei der Serienanlage wird sie automatisch auf den **Basisnamen** gesetzt; am Produkt jederzeit änderbar (z. B. nach Serienanlage von `Ziffern Einzeln - 2 -` auf `Ziffern` korrigieren). In der UI: Filter nach Familie und einklappbare Gruppenköpfe (ohne Familie = „Ohne Familie“). Beim Einführen: einmaliger Vorschlag Familie = Name ohne angehängten Farbnamen (nur wenn Farbe gesetzt und Name so endet), Bestätigung nötig. Unabhängig von Farbe/Tag; nicht der Produktname selbst.
_Avoid_: Nur implizite Gruppierung über Namensähnlichkeit ohne Feld; Familie = Tag; stille automatische Befüllung ohne Nachfrage; Familie = Ziffern-Serien-Basisname belassen wenn kanonisch `Ziffern` gemeint ist

**Materialfamilie**:
Optionale Bezeichnung, unter der zusammengehörige Materialien gruppiert werden — analog zur **Produktfamilie**, aber ein eigenes Feld (nicht dieselbe Liste wie bei Produkten). In der UI: Filter nach Familie und einklappbare Gruppenköpfe (ohne Familie = „Ohne Familie“). Unabhängig von Farbe/Tag/Medium.
_Avoid_: Gemeinsame Familien-Liste mit Produkten; Familie = Tag; nur Gruppierung über Medium/Farbe ohne Feld

**Vorlage** (Produkt):
Ein Produkt, das als Muster für die Serienanlage dient (Stückliste/Tags), markiert durch ein explizites Flag „Ist Vorlage“. Die Serienanlage kopiert davon und setzt je gewählter Farbe ein neues Produkt. Das Flag „Ist Vorlage“ ist nur im **Bearbeiten**-Dialog setzbar, nicht beim Neu-Anlegen.
_Avoid_: Template als UI-Fremdwort; nur „ohne Farbe“ als implizite Vorlage; Vorlage-Schalter im Neu-Anlegen-Dialog

**Serienanlage** (aus Farben):
Auf Knopfdruck Materialien oder Produkte aus gewählten Katalogfarben erzeugen (Auswahl + gemeinsame Defaults). Serien-Materialname = Medium + Farbe; manuell angelegte Materialien frei benennbar. Produktname = Basis + Farbe. Produkt-Serienanlage nutzt optional eine **Vorlage**. Produkt-Mindestbestand: Dialogwert überschreibt, sonst Wert der Vorlage (sonst leer). Material-Serienanlage: optionaler Mindestbestand im Dialog für alle neuen. Materialien: bereits belegte Farben (gleicher color_id) sind nicht wählbar. Produkte: „schon vorhanden“ gilt für den konkreten Namen Basis+Farbe, nicht für die Farbe allein. Katalog-Umbenennung (Medium/Farbe) benennt Artikel um, die noch den alten Seriennamen tragen.
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

**Datensicherung** (Export/Import):
Vollständiger App-Stand als eine JSON-Datei zum Herunterladen und Wiederherstellen (Kataloge, Materialien, Produkte, Bestände, Sets u. a.). Bewegungs-Historie optional per Checkbox (Standard: aus). Beim Import wählt der Nutzer: **Ersetzen** (bestehende Daten werden geleert/ersetzt) oder **Zusammenführen** (Match über Name bzw. SKU/Handle/Farbe+Medium; fehlende anlegen, Stammdaten aktualisieren; Bestände je Standort beim Match **setzen**, nicht addieren) — jeweils mit Bestätigung. Kein Ersatz für Host-Backups der SQLite-Datei.
_Avoid_: Stiller Import ohne Moduswahl; Merge über interne IDs als Normalfall; Bestände beim Merge addieren; nur Excel-CSVs als einzige Sicherung

**Übersicht** (Listen):
Zuerst kritische **Produkte**, darunter kritische **Materialien** (Gesamt ≤ 0 oder unter Mindestbestand). Beide Blöcke ausklappbar und nach **Produktfamilie** bzw. **Materialfamilie** gruppiert. Einzelne kritische Einträge können **ignoriert** werden: sie bleiben dauerhaft aus der Warnliste, bis man sie manuell wieder einblendet. UI-Struktur: Listen/Ansichten als eigene Komponenten, ohne Design-System.
_Avoid_: Übersicht als komplette Material-/Produktverwaltung; Ignorieren nur bis zur nächsten Buchung; befristetes Ausblenden ohne manuelles Wiedereinblenden

**Speichern-Feedback**:
Nach erfolgreichem Speichern erscheint ein kurzer, selbst verschwindender Hinweis (Toast) und der Speichern-Button zeigt kurz „✓ Gespeichert“. Kein blockierender Dialog nur wegen Erfolg.
_Avoid_: Alert/Modal nur für „Gespeichert“; Feedback, das Wegklicken erzwingt

**Filter-Leiste**:
Filter auf den Listen-Seiten stehen oben, rechtsbündig und mit kompakteren Controls — gleiches Verhalten wie bisher, weniger Platzverbrauch. Keine eigene dauerhafte rechte Sidebar und kein nur-per-Icon ausgeklapptes Filterpanel als Pflicht.
_Avoid_: Filter als dominante linke Spalte; Filter verstecken hinter Icon als einzigem Zugang ohne klare Erkennbarkeit

**Bewegungs-Historie**:
Eine nachvollziehbare Umbuchung oder Umwandlung, relevant vor allem mit virtuellen Standorten (MA1, MA2, In Bearbeitung, Ausschuss) und für Umwandlungen — Grundlage für den Überblick „wer hat was / was wurde daraus“.
_Avoid_: Tag-Historie; implizite Umbuchung ohne Eintrag

**Benutzer** / **Login**:
Zugang zur App nur nach Anmeldung (Benutzername + Passwort). Session-Cookie, Idle ca. 12 h. Erster **Admin** per ENV beim Start (`ADMIN_USER` / `ADMIN_PASSWORD`), weitere Benutzer in der Admin-UI. Rollen: **Admin** (volle App) und **Mitarbeiter** (nur Bereich **Bei Mitarbeitern**, Umwandeln Uni→Vintage). Eigenes Passwort änderbar; Admin kann Passwörter setzen und Benutzer deaktivieren.
_Avoid_: Anonymer LAN-Zugriff; Rechte nur über Proxy-Basic-Auth; OAuth als Pflicht für die Manufaktur

