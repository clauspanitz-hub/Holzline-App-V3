# Holzlinge Inventar

Fachsprache für die interne Inventar-, Material- und Stücklistenverwaltung der Holzmanufaktur Holzlinge.

## Language

**Material**:
Ein Rohstoff oder Zulieferteil, das auf Lager liegt und in Stücklisten von Produkten verwendet wird. Einkauf: Menge + Preis der Packung; daraus Preis pro Einheit.
_Avoid_: Rohmaterial, Rohstoff, Bestandteil, Komponente

**Einkaufsmenge**:
Die Menge einer Material-Packung beim Einkauf in der Material-Einheit (z. B. 750 ml).
_Avoid_: Packungsgröße als UI-Fremdwort; Bestellmenge; Nachbestellmenge

**Bestellmenge** (Material):
Optionale typische Nachbestellmenge am Material (bewusst gepflegt). Steuert die Menge neuer Einkauf-Todos: Bestellmenge, sonst zuletzt bestellte Menge, sonst Einkaufsmenge (Packung).
_Avoid_: Einkaufsmenge als Synonym; Fehlmenge als Pflicht-Todo-Menge; Bestellmenge = Mindestbestand

**Bezugsquelle** (Material):
Ein konkreter Shop-Produkt-Link für dieses Material (eigener Link je Material/Farbe). Felder: **Shop** (Katalog), URL, optionale Notiz; mehrere möglich, eine **bevorzugt**. Neue Zeile erst, wenn die vorherige gefüllt ist. In der Link-Übersicht nach Shop gruppiert. Bevorzugte Quelle erscheint im Einkauf-Todo/-Dialog; alle Bezugsquellen sind in der Materialliste als Akzent-Textlinks sichtbar.
_Avoid_: Ein Link für alle Farben desselben Filaments; Lieferanten-CRM; Ersatzartikel als Bezugsquelle

**Shop** (Einkaufskatalog):
Name eines Bezugs-Shops zur Gruppierung von Bezugsquellen. Beim Einfügen einer URL wird der Name aus der Domain vorgeschlagen und bleibt editierbar.
_Avoid_: Shop = Shopify-Herkunft der Bestellung; Shop nur als URL-String ohne Katalog

**Alternativen** (Material):
Freitext-Hinweis zu Ersatzmöglichkeiten (kein Verweis auf andere Material-Stammdaten).
_Avoid_: Gegenseitige Material-Verknüpfung; Alternative = zweite Bezugsquelle

**Produktbezug** (Material):
Welche Produkte dieses Material in der Stückliste nutzen (automatisch) plus optionale Freitext-Notiz.
_Avoid_: Manuell gepflegte Produktliste als alleinige Wahrheit

**Zuletzt bestellt** (Material):
Die Menge des letzten verbuchten Material-Einkaufs. Wird beim Speichern im Einkauf gesetzt; Fallback für Todo-Menge wenn keine Bestellmenge gepflegt ist.
_Avoid_: Manuell Pflichtfeld; ersetzt Bestellmenge ohne Nachfrage

**Einkaufspreis**:
Der Preis für eine komplette Einkaufsmenge (Packung), nicht der Preis pro Verbrauchseinheit.
_Avoid_: Stückpreis (das ist Preis/Einheit); Verkaufspreis

**Verkaufspreis**:
Der aktuelle Verkaufspreis eines **Produkts** in Euro. Unabhängig von **Materialherstellkosten**. In der App am Produkt pflegbar; beim Shopify-CSV übernehmen, wo die Zeile einem Lagerprodukt zuordenbar ist (typisch Variant Price). Leer oder 0 wird ohne Nachfrage gefüllt. Ist schon ein Preis gesetzt und der CSV-Wert weicht ab: zuerst Sammelfrage (**alle CSV** / **alle behalten** / **einzeln**); einzeln öffnet eine Liste je Produkt (bisher vs. CSV) mit denselben Sammelaktionen. **Sets** haben in der App keinen Verkaufspreis (der bleibt am Shop-Listing). Leer oder 0 gilt als unvollständig (`fehlt Verkaufspreis`), ignorierbar wie die anderen `fehlt …`-Tags.
_Avoid_: Verkaufspreis = Materialherstellkosten; Verkaufspreis am Set; nur Shop-Read-only ohne Pflege in der App; leerer Preis ohne Unvollständigkeit; Re-Import überschreibt gesetzte Preise still

**Produkt**:
Ein lagergeführtes Einzelteil der Manufaktur (z. B. Ring in einer Farbe, Kerze, Zahlenstecker), mit eigenem Bestand. Hat einen **Verkaufspreis** (leer/0 = unvollständig).
_Avoid_: Fertigerzeugnis als Shopify-Set, Ware, Variante (als Lagerobjekt); Artikel als Synonym nur für Produkt (Artikel umfasst auch Material)

**Artikel**:
Sammelbegriff für ein lagergeführtes **Produkt** oder **Material**. Kein Set, keine Bestellung, keine SKU.
_Avoid_: Artikel = nur Produkt; Artikel = Set; Artikel = Shop-Listing; Artikel als Synonym für SKU

**Set**:
Eine nur in Shopify (o. ä.) verkaufte **Zusammenstellung aus mehreren Lagerprodukten**; hat selbst keinen Lagerbestand und wird bei Bestellung daraus zusammengestellt. Nicht jedes Shopify-Produkt mit Varianten (Farbe/Motiv) ist ein Set.
_Avoid_: Produkt (für Sets), Bundle als Lagerartikel, fertiges Set auf Lager; jedes variantenfähige Shopify-Produkt automatisch als Set

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
Die Zuordnung, welche Positionen in welcher Menge für eine Einheit benötigt werden. **Produkt-Stückliste:** Materialien und/oder **Produkte** (Komponenten) fürs Fertigen — genau eines je Zeile. **Set-/Varianten-Stückliste:** Materialien und/oder Produkte zum Zusammenstellen.
_Avoid_: Recipe, BOM, Rezept, Bill of Materials (in der UI); Produkt-Stückliste nur Materialien (veraltet)

**Fertigen**:
Der Vorgang, bei dem eine Menge eines Produkts hergestellt wird: Produktbestand steigt; Stücklistenzeilen werden am gewählten Standort abgebucht (Material **oder** Komponenten-Produkt, eine Ebene — keine rekursive Materialabbuchung der Komponenten).
_Avoid_: Produzieren, Herstellen, Buchen (als alleiniger Begriff für diesen Vorgang); Zusammenstellen eines Sets (das ist kein Fertigen auf Set-Ebene)

**Zusammenstellen**:
Bei Bestellung eines Sets die benötigten Komponenten laut Varianten-Stückliste (Produkte und Materialien) an einem gewählten Standort vom Lager abbuchen (ohne Set-Bestand zu erhöhen). Todo unter Werkstatt; Dialog mit BOM-Vorschau; leere Stückliste blockiert die Buchung.
_Avoid_: Fertigen (für Sets), Kommissionieren als alleiniger UI-Begriff (optional synononym); Teilmenge in diesem Schnitt; Set-Lagerbestand

**Bestellung**:
Ein Kundenauftrag mit Positionen. Kein Lagerobjekt und keine Werkstattzeile. Manueller Eingang: **Schnellerfassung** (legt direkt **offen** an; **Datum + Uhrzeit** vorbelegt, änderbar; mindestens eine Position; Kundenname und Nummer optional; Formular auf der Bestellseite zugeklappt hinter Button). Shop-Aufträge: **Shopify-API** zuerst, **Etsy-Mail** als Brücke bis Etsy-API da oder abgelehnt. Shopify-API: nur **bezahlte**, noch nicht vollständig erfüllte Aufträge (unfulfilled oder teilweise erfüllt), nicht storniert; Abruf nur auf Knopfdruck (**Shopify abrufen**), kein laufender Hintergrundabruf; Kundenname aus Shop-Kunde oder Lieferadresse (ohne Kunden-Scope). Alle Positionen eindeutig gematcht (SKU, sonst Name/Farbe) → **offen** und Todos sofort; sonst **zur Prüfung**. **Etsy-Mail:** eigenes Postfach → App-Warteschlange (IMAP); Parse-Knopf (Admin) zuerst neue Mails holen, dann Gemini → immer **zur Prüfung**; Produkt-Vorschläge wie nach Shopify. **Herkunft** folgt dem Eingang (nicht frei umlabeln). Status: **zur Prüfung**, **offen** (mindestens ein offenes Todo), **versandbereit** (keine offenen Todos; Positionen ohne Todo gelten als erfüllt), **versendet**. **Abnicken** setzt **offen** und erzeugt/übernimmt Todos (Fertigen wo nötig; Artikel anlegen für Unzugeordnetes). **Versendet** zuerst manuell an der Bestellung; später zusätzlich aus Shopify fulfilled. **Löschen** erst nach Bestätigung in der App (kein Browser-Dialog). Bleibt sichtbar bis versendet.
_Avoid_: Todo als Synonym für den Shop-Auftrag; Bestellung = einzelne Position; Shop-API/CSV als Voraussetzung für die erste Todo-Liste; Pflicht-Kundenname oder Pflicht-Shopnummer zum Anlegen; nach Werkstatt-Ende ausblenden; Versenden = Fertigen/Zusammenstellen; Versand-Todo; Versendet nur über Shop ohne manuellen Weg; nur Datum ohne Uhrzeit; Herkunft unabhängig vom Import setzen; Eingangsvorschlag als eigenes Objekt neben der Bestellung; geparste Mail erzeugt sofort Todos; versandbereit trotz offener Todos; periodisches Hintergrund-Polling der Shopify-API; stilles Löschen ohne Nachfrage; Etsy-Parse ohne menschliche Prüfung

**Herkunft** (Bestellung):
Woher der Auftrag in die App kam: **Shopify**, **Etsy** oder **Manuell**. Folgt aus dem Eingang (Schnellerfassung, Shopify-API, Etsy-Mail bzw. später Etsy-API). Gleiche Herkunft + Nummer: nicht erneut anlegen. Seltene Kollision mit einer **manuellen** Bestellung derselben Nummer: kein zweites Objekt, Herkunft wird **Shopify**, Positionen bleiben.
_Avoid_: Channel, Kanal als UI-Label; Shop-Name als Herkunft; Herkunft nachträglich frei wählen (Ausnahme nur Manuell → Shopify bei gleicher Nummer); Herkunft nur als Filter ohne die drei Werte

**Zur Prüfung** (Bestellstatus):
Sichtbare Shop-Bestellung. **Shopify-API:** nur wenn mindestens eine Position unzugeordnet oder nicht eindeutig gematcht ist. **Etsy-Mail:** jede geparste Bestellung (Parser kann falsch matchen). Stammdaten und Positions-**Zuordnung** korrigierbar (Produkt, Material oder **Set-Variante** — Set-Zuordnung manuell, kein Auto-Match). Unzugeordnet: Buttons **Produkt erzeugen** (Dialog, kein Todo) und **Auf Liste** (Todo **Artikel anlegen**, sofort unter Todos sichtbar). Unzugeordnet nach Abnicken → Todo **Artikel anlegen**, falls noch keins. **Abnicken** bleibt Pflicht, auch wenn alle Zeilen schon zugeordnet sind — erst dann **offen** und Fertigen-/Zusammenstellen-Todos. Gleiche Herkunft + Nummer = dieselbe Bestellung über Mail und spätere API.
_Avoid_: Eigener Objekttyp „Eingangsvorschlag“; Entwurf unsichtbar in der Bestellliste; Fertigen-Todos schon zur Prüfung; stilles Produkt-Anlegen ohne Button; Abnicken entfällt wenn alles zugeordnet; jeder Shopify-Eingang zwingend zur Prüfung; Etsy-Mail anfangs direkt offen trotz KI-Parser; Schnellerfassung für diesen Weg; CSV-Bestellexport als Ersatz; stilles Auto-Match auf Sets

**Etsy-Mail-Warteschlange**:
Unter Bestellungen: Rohtexte aus dem Spezial-Postfach (jede neue Mail). Seltener Auto-Abruf; Parse-Knopf holt zuerst nach und lässt Gemini alle Wartenden auslesen. Erfolg → Bestellung zur Prüfung, Eintrag weg. Doppel → Hinweis, nur **Ignorieren**. Fehler → bleibt mit Meldung. Secrets nur Server-ENV.
_Avoid_: Gemini bei jedem IMAP-Poll; Mail-Passwort in der App-UI; stilles zweites Anlegen bei gleicher Nummer; Warteschlange als eigener Hauptmenüpunkt

**Aktuelle Bestellungen**:
Bestellungen mit Status **offen** oder **versandbereit** (nicht versendet, nicht **zur Prüfung**). Eigene Liste **oben** auf der Bestellseite (darunter Schnellerfassung, versendete ausklappbar) und in der Übersicht. Bestellungen **zur Prüfung** eigene Liste zum Prüfen/Abnicken, nicht unter Aktuelle.
_Avoid_: Aktuell = nur heute; aktuelle Bestellungen = nur offene Todos ohne Versandbereit; Schnellerfassung über der Auftragsliste; zur Prüfung als laufender Werkstattauftrag in der Übersicht

**Bestellposition**:
Eine Zeile einer Bestellung: zugeordnetes **Produkt**, **Set-Variante**, oder **unzugeordnet** (Freitext), bis ein **Artikel** verknüpft ist. Shop-Titel sollen Variante/Option/Farbe enthalten, soweit der Kanal sie liefert; Personalisierung (z. B. Namen am Gläsertablett) steht in der Bestell-**Notiz**, nicht zwingend im Titel. Erfassung kompakt: Produktwahl, Menge, **Entfernen**. Freitext nur sichtbar, wenn kein Produkt gewählt ist — dann nicht nötig, sobald ein Produkt gesetzt ist. Unzugeordnet (Shop) in der Prüfung: **Produkt erzeugen** öffnet den Produkt-Dialog mit Vorausfüllung (Name/Shop-Titel, SKU, Farbe bei Katalog-Match, Familie/Basis aus Titel als Vorschlag); **Auf Liste** legt höchstens ein Todo **Artikel anlegen** an („vorgemerkt“ wenn schon da). Speichern im Dialog verknüpft die Zeile, merkt die Shop-Zuordnung und erledigt das Todo. Aus diesem Shop-Weg nur **Produkt**, kein Material. Unzugeordnet nach Abnicken ohne Vormerkung → Todo **Artikel anlegen**. Manuelle Freitext-Positionen: Todo kann Produkt oder Material wählen. Shop-Eingang ordnet über **SKU**, sonst **Shop-Zuordnung**, sonst Name/Farbe; sonst **unzugeordnet**. Gemini-**Vorschlag** nach Abruf (sichtbar, **Übernehmen**); Bestätigen speichert Shop-Zuordnung und zieht gleiche Identitäten mit.
_Avoid_: Pflicht, dass der Artikel vor der Bestellung existiert; Freitext ohne Folge-Todo; Freitext-Pflicht neben gewähltem Produkt; Set als einzige Positionsart; Anlegen ohne Verknüpfung an die Position; „Zeile weg“ als Label; Material aus Shop-Produkt-erzeugen; stille Auto-Anlage; zweite Todos derselben Position; jede Shop-Zeile bewusst ohne Match; Set-Variante als Match in diesem Schnitt; Gemini als Gedächtnis; stilles Öffnen durch KI; Gemini bei jeder Tastatureingabe; Vorschlag schon im Auswahlfeld als wäre zugeordnet; Personalisierung nur im Titel erzwingen wenn der Shop sie als Notiz liefert

**Shop-Zuordnung**:
Gemerkte Identität einer Shop-Zeile einer **Herkunft** — Shop-SKU, sonst Shop-Titel plus Variante — zu einem Lagerprodukt. Entsteht nur durch menschliche Bestätigung in **zur Prüfung**, nicht durch Gemini allein. Letzte Bestätigung gewinnt, mit Hinweis wenn sich das Zielprodukt ändert. Zeile wieder unzugeordnet: nur diese Position, die Shop-Zuordnung bleibt. Shop-SKU kommt ans Produkt nur, wenn es noch keine hat. Keine selbst erfundenen SKUs, kein Schreiben nach Shopify. Dieser Schnitt merkt **Shopify** und **Etsy** getrennt (gleiche Herkunft + Identität).
_Avoid_: Alias, Mapping als UI-Wort; Gemini-Speicher; interne SKU-Vergabe; SKU-Sync in den Shop; stilles Überschreiben einer vorhandenen Produkt-SKU; erste Zuordnung unveränderlich ohne Hinweis; Leeren der Zeile löscht das Gedächtnis; Shopify- und Etsy-Titel als dieselbe Identität

**Todo**:
Eine abarbeitbare Werkstatt- oder Beschaffungsaufgabe. **Eigene Menüseite** (nicht nur unter Bestellungen). Filterbar nach Art (Werkstatt vs. Einkauf); Standardansicht Werkstatt. **Fertigen** / Zusammenstellen erst ab Bestellstatus **offen** (nach Schnellerfassung oder nach Abnicken). **Artikel anlegen** auch schon **zur Prüfung**, wenn **Auf Liste** gedrückt wurde — unter Todos sofort sichtbar. Pro **Bestellposition** höchstens die nötigen Todos — **nicht** über Bestellungen hinweg zusammenfassen. Set-Position (verknüpfte Set-Variante) → **Zusammenstellen**; **Fertigen** nur bei On-Demand oder fehlender Fertigware; lagerndes Produkt ohne Unterdeckung → **kein** Werkstatt-Todo; unzugeordnete Position → **Artikel anlegen**. Offene Todos halten die Bestellung auf **offen**, nicht **versandbereit**; an der Bestellung kurzer Hinweis (z. B. offene Fertigen-Anzahl). Aus Bestand (unter Mindestbestand / negativ, Summe **ohne Ausschuss**) → **Einkauf-Todo** nur für Materialien: **sofort automatisch** bei Bestandsänderung erledigen wenn Mindestbestand erfüllt, neu anlegen wenn wieder unterschritten (altes bleibt erledigt); höchstens eines offen pro Material; Knopf **Einkauf-Todos erzeugen** als Bulk/Nachzieh-Hilfe (ADR `0019`, `0023`). Menge aus Bestellmenge / zuletzt bestellt / Einkaufsmenge. Ignorierte Kritische: Auto überspringt; Knopf fragt nach. Abhaken öffnet den Einkauf-Dialog; Speichern erledigt und fragt nach Anpassung der Bestellmenge. Zusammenstellen: Dialog mit Standort und BOM-Vorschau (ADR `0020`).
_Avoid_: Todo = Bestellung; jede Positionszeile immer ein Todo; lagerndes Produkt als Pflicht-Todo; stilles Buchen nur durch Abhaken; Einkaufsliste als zweites, unverbundenes Konzept; eine ungeteilte Mischliste ohne Art; zwei getrennte Listen statt Filter; Fertigen-Todos über Bestellungen mergen; Todos nur unter Bestellungen versteckt; Fertigen-Todos an Bestellungen zur Prüfung; versandbereit trotz offener Todos; Einkauf-Todos für Produkte; offene Einkauf-Todos löschen statt erledigen; Auto-Match von Shop-Zeilen auf Sets in diesem Schnitt



**Materialherstellkosten**:
Die Summe der Materialkosten pro Produkteinheit laut Stückliste (Menge × Einkaufspreis je Material).
_Avoid_: Selbstkosten, Deckungsbeitrag, Verkaufspreis als Synonym für Materialkosten

**Einheit**:
Die Maßeinheit eines Materials aus einer festen, im Code gepflegten Liste (Stk, m, kg, g, m², l, ml).
_Avoid_: Freitext-Einheit, Unit als UI-Begriff

**Mengengenauigkeit**:
Wie fein eine Menge erfasst und angezeigt wird. **Produkte** immer ganzzahlig. **Materialien:** Feld **Nachkommastellen** (0–3) am Material; Standard **0** (ganze Zahlen). Abweichend z. B. Leimholz **2**. Dieselbe Genauigkeit für Bestand, Einkauf, Verbrauch und Stücklistenzeile dieses Materials.
_Avoid_: Drei Nachkommastellen als App-Default; 0,345 eines Produkts; Filament in 0,001 g; alle Materialien automatisch eine Nachkommastelle; Genauigkeit nur an der Einheit oder nur an der Familie

**Standort**:
Ein Ort, an dem Material- oder Produktbestand liegt. Physisch: Hamburg, Dahlenburg; virtuell: In Bearbeitung, MA1, MA2 (bei Mitarbeitern), Ausschuss (verworfen). Material-UI zeigt nur die physischen Standorte (+ Gesamt); Produkte alle Standorte inkl. virtueller.
_Avoid_: Location als UI-Begriff, Bin, Am Waldpark 27 / Werkstatt Rissen / Lager Petra (Shopify-Namen, nicht kanonisch)

**Mindestbestand**:
Optionale Untergrenze je Material oder Produkt. Unterschreitung (oder verfügbarer Bestand ≤ 0 / negativ, ohne Ausschuss) markiert den Artikel als **kritisch** (Fehlmenge): in der Übersicht und zusätzlich in Extra-Blöcken auf den Seiten Materialien und Produkte. Kritische **Materialien** → Einkauf-Todos automatisch bei Bestandsänderung sowie per Knopf (ADR `0019`, `0023`).
_Avoid_: Sollbestand als Pflichtfeld; kritische Übersicht als Ersatz für die Todo-Liste; „Fehlmenge“ als eigenes Objekt neben kritischem Artikel

**Baubare Variante**:
Eine Set-Variante, deren zusammenstellbare Stückzahl sich aus dem über alle Standorte summierten Bestand der Stücklistenzeilen ergibt (`Minimum` über `floor(Bestand/Menge)`). Ob Material-Zeilen mitzählen, ist je Set einstellbar.
_Avoid_: Verfügbarer Set-Bestand (Sets haben keinen Bestand)

**Tag**:
Ein Label zur Gruppierung und Filterung von Materialien und Produkten (mehrere möglich). Einträge kommen aus einem pflegbaren Tag-Katalog; Zuordnung am Artikel. Unabhängig von Farbe/Medium (Art/Option). Beim Setzen an einem Artikel Nachfrage: Tag auch der **gleichen Produkt- bzw. Materialfamilie** geben? Auswahl-UI analog Medium/Farbe (Serienanlage): bereits vorhandene/zutreffende Tags **ausgegraut**.
_Avoid_: Kategorie als einziges Pflichtfeld; Farboption als Tag; stilles Taggen aller Artikel ohne Nachfrage (außer System-Tags für Unvollständigkeit); „alle“ = gesamte Produkt-/Materialliste ohne Familienbezug

**Unvollständigkeit** (Stammdaten):
Fehlende Pflicht-Infos an Material oder Produkt: Material **Mindestbestand** / **Einkaufspreis** (=0); Produkt **Mindestbestand** / **Stückliste** / **Verkaufspreis** (leer oder 0). Die App setzt dazu automatisch die System-Tags `fehlt Mindestbestand`, `fehlt Stückliste`, `fehlt Einkaufspreis`, `fehlt Verkaufspreis` (kataloggeschützt). Ein solcher Tag bleibt, bis das Feld wieder vollständig ist (z. B. Verkaufspreis > 0) **oder** man ihn **bewusst** im Tag-Picker abwählt (= Warnung ignorieren, bis das Feld vollständig und danach erneut unvollständig wird). Speichern des Bearbeiten-Dialogs ohne Tag-Änderung lässt die `fehlt …`-Tags unverändert. Das rote „!“ in der Liste zeigt nur Felder, deren `fehlt …`-Tag noch gesetzt ist.
_Avoid_: Unvollständigkeit nur als unsichtbare Berechnung ohne Filter; Katalog-Umbenennen/Löschen der `fehlt …`-Tags; Familien-Propagierung für System-Tags; Verkaufspreis-Lücke ohne `fehlt Verkaufspreis`; „Fehldaten“ als eigenes Objekt neben Unvollständigkeit; Unvollständigkeit nur in der Übersicht; Speichern von Name/Farbe/Bestand entfernt `fehlt …`-Tags

**Material- / Produktliste**:
Die Hauptliste aller Artikel der jeweiligen Seite. Darüber zwei Extra-Blöcke, tabellarisch: **kritische Artikel** (Fehlmengen) und **Unvollständigkeit** (Fehldaten, inkl. `fehlt Verkaufspreis` bei Produkten), **standard zugeklappt** mit Zähler in der Überschrift. Extra-Tabellen **flach** (keine Familienköpfe; Familie über die Filter-Leiste). Dieselben Begriffe wie in der Übersicht; kein Ersatz für die Hauptliste. Extra-Blöcke folgen derselben **Filter-Leiste** wie die Hauptliste. Schnellbearbeitung: **Mindestbestand**, **Einkaufspreis**, **Verkaufspreis** und Bestand an **Hamburg** und **Dahlenburg** inline. Im Extra-Block **Kritische Artikel**: kein **Bearbeiten**-Knopf (Name öffnet weiter den vollen Dialog); Produkte **Fertigen** (bestehender Dialog); Materialien **Einkauf** (Menge in Material-Einheit, Standort Hamburg vorausgewählt, neuer Einkaufspreis mit altem daneben; speichert Bestand += Menge und aktualisiert Einkaufspreis); **Ignorieren** bleibt. **Unvollständigkeit** behält **Bearbeiten**. Stückliste und der volle Bearbeiten-Dialog bleiben. Virtuelle Standorte nicht in diesen Extra-Tabellen. Mehrere gleiche Lücken auf einmal über **Mehrfachbearbeitung**. Ignorierte kritische Artikel gelten wie in der Übersicht (ausblendbar/wieder einblendbar in den Extra-Blöcken, dieselbe Liste).
_Avoid_: Eine gemischte Problem-Tabelle; Extra-Blöcke statt Hauptliste; andere Labels als in der Übersicht; Fehlmenge/Fehldaten als dritte Sorte neben kritisch/unvollständig; Inline-Stückliste; Extra-Tabelle mit MA1/MA2/Ausschuss; nur Dialog ohne Inline; physischer Bestand in den Extra-Blöcken nur über Umbuchen; Extra-Blöcke ignorieren den Katalogfilter; Extra-Blöcke standard aufgeklappt; Extra-Blöcke nach Familie gruppiert; Bearbeiten-Knopf in Kritische Artikel; Einkauf als „Buchen“; Fertigen/Einkauf in Unvollständigkeit oder Übersicht

**Farbe**:
Ein benannter Farbeintrag im Katalog (z. B. Rot, Salbeigrün), jeweils mit einem Medium und einem optionalen **Hex-Wert** für die Darstellung (Filter-Kästchen, Hover = Name). Ohne Hex: graues Kästchen. Erstzuweisung der Hex-Werte aus den Farbnamen; danach im Katalog änderbar. Material und Produkt können je eine Farbe haben. In der UI: Medium zuerst, dann Farbe/Option.
_Avoid_: Farb-Tag statt Katalogeintrag; „Variante“ oder „Art“ für Farboptionen (Variante = Set; Art nicht mehr als UI-Alias); Farbe nur als Name ohne darstellbaren Wert wo Kästchen gemeint sind

**Medium** (Farbe):
Die Art der Farbgebung aus einem pflegbaren Katalog (Start: Lack, PLA). Am Artikel und in Katalogen erscheint **Medium** oberhalb der Farbe; im Katalog je Medium eine eigene Farb-Tabelle. Vorschläge und Matching nur innerhalb desselben Mediums. Katalog-Bereich: **Medien**.
_Avoid_: Materialart, Farbtyp; UI-Label „Art“ (veraltet); „Art“ als eigenes Domänenobjekt neben Medium

**Mehrfachbearbeitung**:
Gleichzeitiges Setzen ausgewählter Felder für mehrere Materialien oder Produkte, in der UI als **Aktionsblöcke** (Feld und zugehörige Controls gruppiert). Auswahl: Checkboxen in der **Hauptliste** und in den **Extra-Blöcken** (eine gemeinsame Auswahl auf der Seite) und/oder „ganze Produkt-/Materialfamilie“. Erlaubt ohne Extra-Warnung: Mindestbestand, Tags, bei Produkten **Verkaufspreis**; bei Produkten und Materialien **Ist-Vorlage**; bei Produkten zusätzlich Produktfamilie; bei Materialien zusätzlich Materialfamilie. Mit **warnender Nachfrage** vor dem Speichern außerdem: **Bestand** (gleicher Absolutwert an einem gewählten Standort), **Stückliste** (eine Zeile **hinzufügen/ändern** oder **entfernen**: Komponente ist Material oder Produkt; Entfernen ohne Menge; fehlt die Zeile beim Produkt → überspringen und zählen; übrige Zeilen bleiben) und **Löschen** der gesamten Auswahl. Löschmodus deaktiviert die übrigen Blöcke; nicht löschbare Einträge (z. B. Material in Produkt-Stückliste) werden übersprungen und gemeldet. Nicht per Mehrfach: Name, Farbe.
_Avoid_: Massen-Umbenennung; Massen-Farbänderung; Bestand/Stückliste/Löschen ohne Warn-Dialog; Mehrfach-Bestand als Delta; Mehrfach-Stückliste als komplettes Ersetzen aller Zeilen; Bearbeiten und Löschen in einem Speichern-Schritt mischen; zweite Bulk-Leiste nur an den Extra-Blöcken; Extra-Auswahl getrennt von der Hauptliste; Verkaufspreis nur einzeln, nie in der Mehrfachbearbeitung

**Produktfamilie**:
Optionale Bezeichnung, unter der zusammengehörige Produkte gruppiert werden (z. B. alle Einzelziffern unter **`Ziffern`**). Bei der Serienanlage wird sie automatisch auf den **Basisnamen** gesetzt; am Produkt jederzeit änderbar (z. B. nach Serienanlage von `Ziffern Einzeln - 2 -` auf `Ziffern` korrigieren). In der UI: Filter nach Familie und einklappbare Gruppenköpfe, **Standard geschlossen**. Dieselbe Gruppierung in **Auswahllisten** (eigene Liste mit zuklappbaren Familien, nicht natives Select). Ohne Familie = „Ohne Familie“. Beim Einführen: einmaliger Vorschlag Familie = Name ohne angehängten Farbnamen (nur wenn Farbe gesetzt und Name so endet), Bestätigung nötig. Unabhängig von Farbe/Tag; nicht der Produktname selbst.
_Avoid_: Nur implizite Gruppierung über Namensähnlichkeit ohne Feld; Familie = Tag; stille automatische Befüllung ohne Nachfrage; Familie = Ziffern-Serien-Basisname belassen wenn kanonisch `Ziffern` gemeint ist; Familien in Listen standardmäßig aufgeklappt; flache Selects wo Familien existieren

**Materialfamilie**:
Optionale Bezeichnung, unter der zusammengehörige Materialien gruppiert werden — analog zur **Produktfamilie**, aber ein eigenes Feld (nicht dieselbe Liste wie bei Produkten). Bei der Serienanlage wird sie automatisch auf den **Basisnamen** gesetzt (wie bei Produkten); am Material jederzeit änderbar. In der UI: Filter nach Familie und einklappbare Gruppenköpfe, **Standard geschlossen** — analog zur **Produktfamilie** (gleiche Auswahllisten-Gruppierung). Ohne Familie = „Ohne Familie“. Unabhängig von Farbe/Tag/Medium.
_Avoid_: Gemeinsame Familien-Liste mit Produkten; Familie = Tag; nur Gruppierung über Medium/Farbe ohne Feld; Familien standardmäßig aufgeklappt

**Vorlage** (Produkt oder Material):
Ein Artikel, der als Muster für die Serienanlage dient, markiert durch ein explizites Flag „Ist Vorlage“. Beim **Produkt**: Stückliste und Stammdaten (Tags, Mindestbestand). Beim **Material**: Stammdaten ohne Stückliste (Einheit, Einkaufsmenge/-preis, Tags, Mindestbestand). Die Serienanlage kopiert davon und setzt je gewählter Farbe einen neuen Artikel. Das Flag ist nur im **Bearbeiten**-Dialog setzbar, nicht beim Neu-Anlegen. Im Material-Serien-Dropdown: alle Material-Vorlagen wählbar, Vorlagen des aktuellen Medium-Filters zuerst.
_Avoid_: Template als UI-Fremdwort; nur „ohne Farbe“ als implizite Vorlage; Vorlage-Schalter im Neu-Anlegen-Dialog; Material-Vorlage mit Stückliste; Vorlagen-Dropdown nur Medium-gefiltert ohne andere Medien

**On-Demand-Produkt**:
Ein **Produkt** mit Stückliste, das vor allem auf Bestellung gefertigt wird; Fertigbestand ist oft 0. „Machbar“ richtet sich nach der **Material-Baubarkeit** über die Stückliste (nicht nach Fertigware auf Lager). Im Shopify-CSV-Assistenten als eigene Markierung wählbar; in der **Import-Warteschlange** Typ On-Demand. Beim Anlegen über die Serienanlage wird das Produkt-Flag **On-Demand** gesetzt. Anzeige (Badge/Liste) und Machbarkeits-Übersicht folgen später.
_Avoid_: Als Set modellieren nur weil Shopify es verkauft; Machbarkeit nur über Fertigbestand; Markierung ohne Flag am Produkt verlieren

**Shopify-CSV-Assistent**:
Einlesen eines Shopify Produkte-Exports. Pro Handle: **Set**, **Produkt-/Material-Serie**, **On-Demand** oder **ignorieren** — kein stilles Anlegen. Ignorierte Handles → **Ignorieren-Liste**; in der normalen Übersicht ausgeblendet, bis Ignorieren aufgehoben; von der Liste aus später bearbeitbar. Ignorieren ist **dauerhaft pro Handle** (überlebt erneute CSV-Uploads), bis manuell zurückgeholt. **Set:** Options-Zuordnung. **Serie / On-Demand:** Eintrag in die **Import-Warteschlange** (nicht still anlegen). Bei mehreren Options-Achsen ohne Set: eine Achse = Variante, übrige in den **Basisnamen**. Falsch importierte Sets: Aufräumen per Auswahlliste. **Variant Price** → **Verkaufspreis** am zuordenbaren Lagerprodukt (leer/0 füllen; sonst Sammelfrage, optional Einzel-Liste).
_Avoid_: Jedes Varianten-Produkt automatisch als Set; stilles Anlegen; Ignorieren = endgültig löschen ohne Wiederaufnahme; Ignorieren nur sitzungsweit; Inventar-Export als einzige Quelle; CSV-Preis überschreibt gesetzte Verkaufspreise ohne Nachfrage

**Import-Warteschlange**:
Persistente Liste der Shopify-Handles, die im Assistenten als **Serie Produkt**, **Serie Material** oder **On-Demand** markiert wurden — noch keine Lagerartikel. Eigener UI-Tab. Pro Handle höchstens ein Eintrag: erneute Assistenten-Markierung **aktualisiert** offene Einträge (Titel/Optionen); erledigte bleiben, bis erneut markiert → dann wieder offen mit neuen Daten. Von dort aus die bestehende **Serienanlage** öffnen: zuerst **Medium** wählen, Shopify-Farbwerte gegen dessen **Katalogfarben** mappen (Aliase, Mehrdeutigkeit → Dropdown); **Vorlage** optional danach. Bei mehreren Optionsachsen: Nutzer wählt „Diese Option ist die Farbe“; übrige Achsen/Werte → **Basisname**. Vorbelegung Basisname + gematchte Farben. Nach Speichern in der Serienanlage Nachfrage **„Als erledigt markieren?“** (Standard: ja) — auch bei Teilserien; bei Ja: Status **erledigt** (ausgegraut, filterbar, löschbar); bei Typ On-Demand zusätzlich Produkt-Flag setzen. **Verwerfen** entfernt sofort. Offene Einträge bleiben bis erledigt oder verworfen. On-Demand-Anzeige/Machbarkeit in der Produktliste später.
_Avoid_: CSV-Import als fertige Produkte; nur sitzungsweite Vormerkung; Warteschlange = Sets; Farben ohne Medium-Bezug anlegen; Medium nur aus Vorlage ableiten; eigenen Import-Dialog statt Serienanlage; Warteschlange nur unter Sets verstecken; nach Anlegen sofort löschen ohne Erledigt-Status; Farb-Achse still raten; On-Demand-Markierung ohne Flag am Produkt; Duplikat-Einträge pro Handle; still erledigt ohne Nachfrage bei Teilserie


**Serienanlage** (aus Farben):
Auf Knopfdruck Materialien oder Produkte aus gewählten Katalogfarben erzeugen (Auswahl + gemeinsame Defaults). Name = **Basis + Farbe** (Basis im Dialog). Mit **Vorlage**: Basis aus Vorlagenname ohne Farbsuffix vorbelegen (Farbe am Namensende abschneiden), Stammdaten/Tags/Stückliste wie bisher. Ohne Vorlage: Basis manuell. „Schon vorhanden“ gilt für den konkreten Namen Basis+Farbe, nicht für die Farbe allein. Material Einheit/Einkauf: Dialog oder Vorlage. Tags: Vorlage plus Dialog (Merge). Manuell angelegte Artikel frei benennbar. Katalog-Umbenennung (Medium/Farbe) benennt Artikel um, die noch den alten Medium+Farbe-Seriennamen tragen.
_Avoid_: Automatisches Anlegen ohne Nachfrage; Serien-Material immer nur Medium+Farbe; Vorlage-Tags verwerfen wenn Dialog leer; Produkt-Serie ohne Tag-Kopie von der Vorlage

**Umwandlung**:
Der Bestandstausch von einem **Quellprodukt** zu einem **Zielprodukt** am selben Standort (z. B. Uni-Geburtstagsring → Vintage-Geburtstagsring nach Bemalen). Kein Fertigen und kein Umbuchen. Die Umwandlung wird nur angeboten, wenn der Produktname „Uni“ als Wort enthält; das Ziel ergibt sich automatisch, indem „Uni“ im Namen durch „Vintage“ ersetzt wird (exakter Produktname). Die Farbe bleibt die des Quellprodukts.
_Avoid_: Umbuchen für Produktwechsel; Tag als Status „wird Vintage“; stillschweigende Hintergrund-Umbuchung als Ersatz; Umwandeln ohne „Uni“ im Namen; manuelles „Wird zu“-Feld

**Quellprodukt / Zielprodukt**:
Kein Pflegefeld mehr. Typisch: Name mit „Uni“ → gleichnamiges Produkt mit „Vintage“ statt „Uni“. Fehlt das Vintage-Produkt, ist Umwandeln nicht möglich (Hinweis anlegen).
_Avoid_: Paarung nur über Freitext-Ähnlichkeit ohne klare Uni→Vintage-Ersetzung; Uni/Vintage als Zustand desselben Produkts; Pflicht-Verknüpfung in der UI

**Ausschuss** (Standort):
Virtueller Standort für verworfenen Produktbestand (nicht mehr Uni, nicht Vintage). Bestand liegt dort weiter und ist nachvollziehbar; er ist kein verkaufbarer Lagerort. Zählt in der Produkt-Gesamtmenge mit, aber nicht als verfügbarer/baubarer Bestand.
_Avoid_: Stilles Löschen ohne Spur; Tag „Ausschuss“ statt Standort; Ausschuss als Zustand am Produkt

**Bei Mitarbeitern** (Überblick):
Eigene Ansicht für Produkte mit Bestand > 0 an MA1/MA2, inkl. Zugang zur Bewegungshistorie. Kein Ersatz für die normale Produktliste und **kein** Produkt-Bearbeiten von dort (Stammdaten nur unter Produkte). Der Knopf Umwandeln erscheint nur bei „Uni“ im Namen und vorhandenem Vintage-Ziel.
_Avoid_: Nur Tabellenfilter statt eigener Überblick; Tags als alleinige „bei MA“-Anzeige; Bearbeiten-Dialog auf Bei Mitarbeitern; Stammdaten-Pflege im MA-Überblick; Anzeige nur bei manuellem „Wird zu“

**Datensicherung** (Export/Import):
JSON-Datei für **Inventar** (Kataloge, Materialien, Produkte, Bestände, Sets u. a.) zum Herunterladen und Wiederherstellen — nicht Bestellungen, Todos, Shop-Zuordnungen, Tageslage oder Benutzer (dafür Host-Backup der SQLite). Bewegungs-Historie optional per Checkbox (Standard: aus). Beim Import wählt der Nutzer: **Ersetzen** (bestehende Daten werden geleert/ersetzt) oder **Zusammenführen** (Match über Name bzw. SKU/Handle/Farbe+Medium; fehlende anlegen, Stammdaten aktualisieren; Bestände je Standort beim Match **setzen**, nicht addieren) — jeweils mit Bestätigung. Kein Ersatz für Host-Backups der SQLite-Datei.
_Avoid_: Stiller Import ohne Moduswahl; Merge über interne IDs als Normalfall; Bestände beim Merge addieren; nur Excel-CSVs als einzige Sicherung; Datensicherung als vollständiger Ersatz für die ganze SQLite inkl. Bestellungen

**Übersicht** (Listen):
Eigene Abschnitte (wie **Datensicherung**, nicht nur Toggles in einem Panel), von oben: **Aktuelle Bestellungen** und offene **Todos** aus Bestellungen **standard aufgeklappt** (Zuklappen optional); darunter die **Tageslage**; dann **kritische Artikel** und **Unvollständigkeit** **standard zugeklappt**. Einzelne kritische Einträge können **ignoriert** werden (Übersicht und Extra-Blöcke Materialien/Produkte, dieselbe Liste). Keine Filter-Leiste auf dieser Seite.
_Avoid_: „fehlender Artikel“ als Synonym für Todo Artikel anlegen; Übersicht als komplette Material-/Produktverwaltung; Ignorieren nur bis zur nächsten Buchung; befristetes Ausblenden ohne manuelles Wiedereinblenden; Übersicht ohne Bestellungen/Todos/Tageslage/Unvollständigkeit; alle Abschnitte in einem Panel; Filter-Leiste auf der Übersicht; Bestellungen/Todos standard zugeklappt; Ignorieren nur in der Übersicht, Extra-Blöcke zeigen Ignorierte trotzdem

**Tageslage**:
Abschnitt auf der Übersicht unter Bestellungen/Todos: von der App berechnete Kennzahlen (aktuelle Bestellungen, offene Todos nach Art, zur Prüfung) plus von Gemini einmal pro Kalendertag erzeugter Fließtext (Todo-Produkte namentlich), motivierender **Spruch des Tages** und 2–3 Schritte **Als Nächstes** (zuerst echte offene Todos/Prüfung; bei wenig Lage holzlinge-passende Motivationsideen nur als Text). Todo-Schritte verweisen auf bestehende Todos; Ideen legen keine Todos an. Manuell **Aktualisieren** erneuert den Tages-Cache. Ohne Gemini, bei Kontingent oder Fehler: Kennzahlen trotzdem; **Als Nächstes** aus offenen Todos (Fallback); Spruch/Hinweis statt leerem Block. Später erweiterbar um Preise/Kosten/Zeiten.
_Avoid_: KI-erfundene Kennzahlen; neuer Todo-Datensatz aus Motivationsideen; Gemini bei jedem Seitenaufruf ohne Cache; Tageslage oberhalb der Bestellungen; Preise/Kosten als Pflicht in diesem Schnitt; leere Nächste Schritte wenn Gemini ausfällt

**Speichern-Feedback**:
Nach Speichern (und anderen Aktionen) erscheint ein Hinweis in der **Toast-Liste** (gestapelt, mit Zeitstempel). Toasts bleiben bis zum Tippen; bei bekanntem Ziel optional Nachfrage **„Zur Stelle?“** und Navigation (ADR `0024`). Der Speichern-Button zeigt kurz „✓ Gespeichert“. Kein blockierender Dialog nur wegen Erfolg.
_Avoid_: Alert/Modal nur für „Gespeichert“; Auto-Dismiss, der Hinweise zu früh verschwinden lässt; mehrere Toasts übereinander an derselben Fixed-Position ohne Stack

**Filter-Leiste**:
Unter der Hauptnavigation, **nur** auf Materialien und Produkte (nicht auf der Übersicht). Eine Zeile (notfalls zwei): **Farbe** immer **mit Medium**, aufklappbar — mehrere Medien gleichzeitig möglich; nach Wahl eines Mediums dessen Farben als Kästchen (Hover = Name). Medium-Treffer = Farbe dieses Mediums **oder** Familienname = Mediumname **oder** Tagname = Mediumname (Groß-/Kleinschreibung egal). Keine Farbe gewählt = alle Farben des Mediums plus Familie-/Tag-Namensgleichheit; eine oder mehrere Farben = nur Artikel mit genau diesen Farben (Familie-/Tag-Treffer ohne diese Farbe fallen raus). Medium und Farbe setzen **nicht** automatisch Familie oder Tag. **Familie** und **Tag** als Mehrfach-Auswahl; plus **Freitext**. Auf **Materialien** zusätzlich Toggle **Negativbestand** (an/aus): nur Einträge mit `is_negative` (Gesamt < 0 oder ein Standort < 0 — wie Backend/Übersicht). Innerhalb einer Filterart **ODER**, zwischen den Arten **UND**. **Ein gemeinsamer Filterstand** über Materialien und Produkte (Negativbestand-Toggle nur auf Materialien sichtbar und nur dort wirksam); auf der jeweiligen Seite gelten Filter für **Hauptliste und Extra-Blöcke**. Sichtbarer Hinweis, wenn Filter aktiv sind, und eine Aktion **alle Filter entfernen**. Nicht auf Übersicht/Bestellungen/Todos/Sets/Import.
_Avoid_: Filter als dominante linke Spalte; Filter verstecken hinter Icon als einzigem Zugang; Filterleiste auf der Übersicht oder auf Bestellungen; Filter ohne Hinweis/Reset bei aktivem Stand; flache Farbliste über alle Medien; Farbe ohne Medium im Filter; nur ein Medium gleichzeitig im Filter; Medium-Wahl setzt Familie/Tag automatisch mit; Familie = Tag; Extra-Blöcke auf Material/Produkt ohne Filter; Medium-Filter nur über gespeicherte Farbe ohne Familien-/Tag-Namensgleichheit; Negativbestand-Filter ohne Toggle in der bestehenden Leiste

**Bewegungs-Historie**:
Eine nachvollziehbare Umbuchung oder Umwandlung, relevant vor allem mit virtuellen Standorten (MA1, MA2, In Bearbeitung, Ausschuss) und für Umwandlungen — Grundlage für den Überblick „wer hat was / was wurde daraus“.
_Avoid_: Tag-Historie; implizite Umbuchung ohne Eintrag

**Benutzer** / **Login**:
Zugang zur App nur nach Anmeldung (Benutzername + Passwort). Session-Cookie, Idle ca. 12 h. Erster **Admin** per ENV beim Start (`ADMIN_USER` / `ADMIN_PASSWORD`), weitere Benutzer in der Admin-UI. Rollen: **Admin** (volle App) und **Mitarbeiter** (nur Bereich **Bei Mitarbeitern**, Umwandeln Uni→Vintage). Eigenes Passwort änderbar; Admin kann Passwörter setzen und Benutzer deaktivieren.
_Avoid_: Anonymer LAN-Zugriff; Rechte nur über Proxy-Basic-Auth; OAuth als Pflicht für die Manufaktur

