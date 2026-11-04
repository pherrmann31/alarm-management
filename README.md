# Alarm Management v1.0 – erster Testrelease

Version **1.0.0b1**, Ziel Home Assistant Core 2026.10.4. Reale Geräteaktionen sind aktiviert. Die automatische Aufnahme ist zunächst ausgeschaltet und wird einmal mit passenden Alarmzielen eingerichtet.

## Enthalten

- Einzelquellen und nicht verschachtelte Meldergruppen; mindestens ein oder alle Mitglieder.
- Geschützte Standardgruppen und automatische Gesamtauswahlen für Rauchmelder und Hausalarmtaster.
- Automatische Aufnahme bestehender und neuer geeigneter HA-Entitäten während des Betriebs, stabile Identitäten und keine erneute automatische Aufnahme derselben Entität.
- Rauchmelder anhand `binary_sensor` und Geräteklasse `smoke`. Batterie-Entitäten werden ausdrücklich ausgeschlossen, auch wenn der Name „Smoke Alarm“ enthält.
- Hausalarm über konkrete Namensmuster bzw. HA-Label-ID und passenden Zustands-/Ereignistyp. MQTT und Zigbee werden über die bereits eingerichteten HA-Integrationen eingebunden.
- Neue automatische Quellen landen in der passenden Standardgruppe; manuelles Verschieben bleibt erhalten. Gesamtauswahlen behalten die Quelle unabhängig von der Raumgruppe.
- Ausgabegruppen und Benachrichtigungsgruppen. Eine Regel kann direkte Ausgaben und Gruppen gemeinsam anfordern; doppelte IDs werden zusammengeführt.
- Automatische Einrichtungsregeln mit ausgewählten Alarmzielen. Bereits aktive neu aufgenommene Rauchmelder werden ausgewertet.
- Native HA-Ereignis-Entitäten für Taster; neue Ereignisse werden kurz als Eingang ausgewertet und anschließend als Alarmvorfall gespeichert. Alte Ereigniszeitstempel werden beim Neustart nicht erneut ausgelöst.
- Bestehende Vorfälle, Quittierung, Reset mit Fehlerbegründung, Browser-Pop-up-Quittierung, Ausgabefehler und erneuter Versand fehlgeschlagener Ausgaben bleiben verfügbar.
- Regelpriorität 0–5 bestimmt die Reihenfolge gemeinsamer Textausgaben. Sie unterdrückt keine anderen Alarmanforderungen.
- Gemeinsame Schaltausgänge bleiben eingeschaltet, solange mindestens eine zugeordnete Regel EIN anfordert.
- Eigener Sensor „Gestörte Eingänge“, begrenzte Diagnoseattribute und Protokoll automatischer Aufnahmen.
- Gruppenvorschau zur Prüfung der Regel- und Ausgabeverteilung ohne Geräteaktionen oder Nachrichtenversand.

## Erste Einrichtung

1. Zuerst die benötigten Ausgänge und Benachrichtigungen anlegen. Optional Ausgabe- oder Benachrichtigungsgruppen unter „Gruppen & automatische Aufnahme“ bilden.
2. „Rauchmelder automatisch aufnehmen“ öffnen. Die gefundenen Rauchalarm-Entitäten prüfen, Alarmziele auswählen und Aufnahme aktivieren.
3. Dadurch entsteht bzw. aktualisiert sich „Feueralarm – alle Rauchmelder“. Neue passende Geräte werden ohne HA-Neustart aufgenommen; die Suche wird kurz gebündelt ausgeführt.
4. Gruppen wie Erdgeschoss und Obergeschoss anlegen. Unter „Melder verschieben“ Quellen zuordnen. Die allgemeine Feueralarmregel bleibt wirksam, weil sie „Alle Rauchmelder“ verwendet.
5. Für zusätzliche Regeln die gewünschten Einzelquellen oder Gruppen auswählen. Gruppenmodus und Regelmodus sind getrennte Bedingungen. Leere oder vollständig unbekannte Gruppen gelten nicht als „alles in Ordnung“.
6. „Verteilung prüfen“ berechnet einen hypothetischen Alarm aller aktivierten Gruppenmitglieder. Es wird dabei nichts geschaltet oder versendet; echte Zustellung muss separat geprüft werden.

## X-Sense über MQTT

Die bestehende MQTT-Anbindung muss den eigentlichen Rauchalarm als HA-Binärsensor mit Geräteklasse `smoke` bereitstellen. Herstellername oder Gerätebezeichnung allein genügen nicht. Die Entität „Battery Status“ mit „Anzeigen als: Batteriestand“ ist kein Rauchalarmeingang. Geräteraum und Meldername werden aus HA übernommen. Für den einzelnen Alarm kann ein eigener Name vergeben werden.

## Hausalarmtaster

Unter „Hausalarmtaster automatisch aufnehmen“ ein enges Namensmuster wie `event.hausalarm_*` oder eine HA-Label-ID eintragen. Sind beide gesetzt, müssen beide passen. Bei `event`-Entitäten einen vom Gerät angebotenen Ereignistyp verwenden, beispielsweise `single`. Bei einem Zustandsmelder den tatsächlichen Rohzustand, beispielsweise `on`, verwenden. Anschließend Alarmziele wählen und aktivieren.

Die automatische Vorlage gilt für die angegebenen Kriterien und einen Auslösewert. Unterschiedliche Tastentypen können weiterhin einzeln konfiguriert werden. Mehrere gleichzeitig verwaltete automatische Tastervorlagen sind in diesem Testrelease noch nicht enthalten. Unverarbeitete MQTT-Payloads oder reine ZHA-Busereignisse werden nicht direkt abonniert; hierfür muss die vorhandene Anbindung eine passende HA-Entität bereitstellen. Ereignisse vor der Aufnahme einer Quelle werden nicht nachträglich als Tastendruck interpretiert.

## Verhalten und Grenzen

- Vorfälle werden weiterhin pro Regel gespeichert. Mehrere Melder derselben Gruppenregel ergänzen diesen Vorfall. Unterschiedliche Regeln werden nicht automatisch zu einem einzigen Vorfall verschmolzen.
- Prioritäten ordnen gemeinsame Texte; die konfigurierten Textvorlagen und Zielgrenzen gelten weiterhin. Zu lange Texte erzeugen einen sichtbaren Fehler, keine stille Abschneidung.
- Benachrichtigungsgruppen bündeln konfigurierte Benachrichtigungsausgänge mit ihren eigenen Empfängern und Texten. Zwei verschiedene Nachrichtendefinitionen an dasselbe Handy bleiben zwei beabsichtigte Nachrichten.
- Quittierung bestätigt einen Alarm; Reset prüft aktive bzw. unklare Ursachen. Änderungen der Mitgliedschaft löschen keinen gespeicherten Vorfall.
- Beim Löschen eines noch gruppierten Eintrags wird auf die bestehende Mitgliedschaft hingewiesen. Eine manuell gelöschte automatische Quelle wird von erneuter Aufnahme ausgeschlossen; bei Bedarf kann sie manuell wieder angelegt werden.
- Gruppen sind nicht verschachtelt. Unterstützt werden bis zu 1000 Eingänge, 1000 Regeln, 200 Ausgaben und 200 Gruppen; dies sind Validierungsgrenzen, keine gemessene Hardwarekapazität.
- Normale Zustandsänderungen und neue Geräte werden im Betrieb verarbeitet. Das Speichern von Konfigurationen lädt die Integration neu, ohne vollständigen HA-Neustart.
- Ein frischer oder leerer `event`-Eingang mit Zustand `unknown` bedeutet noch kein empfangenes Ereignis. `unavailable` ist eine Störung.
- Der Versandstatus bestätigt den HA-Serviceaufruf, nicht die Anzeige auf einem physischen Endgerät.
- Noch ausstehend für den endgültigen v1.0-Umfang: mehrere automatische Tastervorlagen, ein zusammenhängender Einrichtungsassistent mit abschließender Gesamtvorschau und detailliertes Änderungsprotokoll für sämtliche manuellen Gruppenänderungen. Vollständig dynamische Bereichs-/Etagenmitgliedschaft ist ebenfalls noch nicht enthalten; Raumgruppen werden manuell verwaltet.

## Update und Veröffentlichung

Vor dem Test ein vollständiges HA-Backup erstellen, das Konfiguration und `.storage` enthält. Bestehende Integration nicht löschen. Vorhandene Quellen, Regeln und Ausgaben bleiben erhalten; die neuen Gruppen werden ergänzend geführt. Ein Rückweg nach v0.9 erfolgt über das vollständige vorherige Backup, da ältere Versionen neue Gruppenregeln und Protokollereignisse nicht verstehen.

GitHub-Paket an der Repository-Wurzel entpacken: Dort liegen `hacs.json`, README und `custom_components/alarm_management/`. Den inneren Integrationsordner nicht direkt an die Repository-Wurzel kopieren. Änderungen auf einem eigenen Entwicklungszweig committen und veröffentlichen. GitHub-Release mit Tag `v1.0.0b1` erstellen, Ziel ist dieser Zweig. Als **Pre-release** markieren. Kein bestehendes Tag verschieben.

In HACS Alarm Management öffnen, Informationen aktualisieren und bei „Erneut herunterladen“ diese Testversion auswählen; gegebenenfalls Beta-Versionen anzeigen. Nach dem Dateiupdate HA neu starten. Danach zeigt die Integration 1.0.0b1 an.

## Praktische Abnahme

1. Tatsächliche X-Sense-Rauchalarm-Entität prüfen: `smoke`; die Batterie-Entität darf nicht aufgenommen werden.
2. Aufnahme aktivieren, Testmelder kontrolliert auslösen, Quelle und Bereich prüfen sowie Sirene/Display/Handy testen.
3. Melder nach EG verschieben; allgemeine Feueralarmregel muss weiterhin reagieren.
4. Weiteren passenden Melder hinzufügen; er muss automatisch in Standard erscheinen und dieselben Alarmziele verwenden.
5. Zwei Melder und zwei Regeln gleichzeitig testen: Quittierung und Reset eines Zusammenhangs dürfen andere Alarmanforderungen nicht verlieren.
6. Tasterereignis testen, anschließend Integration und HA neu starten: kein erneuter Alarm durch den alten Ereigniszeitstempel.
7. Nichterreichbaren Melder und fehlgeschlagene Ausgabe prüfen; beide müssen verständlich sichtbar sein.

Die eigenständige Alarmfunktion der Rauchmelder muss unabhängig von Home Assistant erhalten bleiben. Dieser Testrelease wurde nicht mit deinen physischen Geräten oder einem laufenden HA-Core geprüft.
