# Alarm Management

**Alarme sammeln, gemeinsam auswerten und gezielt verteilen – direkt in Home Assistant.**

Alarm Management verbindet Rauchmelder, Hausalarmtaster und weitere Zustandsquellen mit konfigurierbaren Regeln. Diese steuern Sirenen, Statusanzeigen und Benachrichtigungen. Du legst fest, welche Quellen zusammengehören und wer bei einem Alarm informiert wird.

**Dokumentationsstand: v1.2.0 · Home Assistant Core ab 2026.10.4 laut HACS-Konfiguration · Custom Integration in Entwicklung**

[Releases](https://github.com/pherrmann31/alarm-management/releases) · [Fehler melden](https://github.com/pherrmann31/alarm-management/issues) · [Prüfbericht](VALIDATION.md)

## So funktioniert es

**Einzelmelder oder Meldergruppen → Regeln → gespeicherte Alarmvorfälle → Ausgänge und Benachrichtigungen**

Beispiel: Ein Rauchmelder in der Küche löst aus. Die Regel „Feueralarm – alle Rauchmelder“ fordert die Sirene an, schreibt den Alarmtext auf eine Anzeige und benachrichtigt die ausgewählten Handys. Meldet später auch der Flur Rauch, ergänzt dieser Melder den Vorfall derselben Regel.

| Baustein | Aufgabe | Beispiel |
| --- | --- | --- |
| Eingangsquelle | Zustand oder Tastenereignis erfassen | Rauchmelder Küche, Hausalarmtaster Flur |
| Meldergruppe | Mehrere Eingänge gemeinsam auswerten | Rauchmelder Erdgeschoss |
| Regel | Bedingungen und Alarmziele verbinden | Mindestens ein Rauchmelder löst aus |
| Ausgabegruppe | Konfigurierte Ausgänge bündeln | Sirene, Warnlicht und Display |
| Benachrichtigungsgruppe | Konfigurierte Nachrichten bündeln | Handys der Familie und Wandtablets |

## Funktionen

- Einzelne Eingänge sowie Meldergruppen mit „mindestens ein Mitglied“ oder „alle Mitglieder gleichzeitig“.
- Automatische Aufnahme geeigneter Rauchmelder und Hausalarmtaster nach einmaliger Einrichtung.
- Standardgruppen für neue Geräte und manuell verwaltete Raumgruppen wie Erdgeschoss oder Obergeschoss.
- Regeln mit direkten Alarmzielen oder Ausgabe- und Benachrichtigungsgruppen.
- Gespeicherte Alarmvorfälle mit auslösenden Meldern, Bereichen, Quittierung und Reset.
- Anzeige gestörter Eingänge sowie Protokolle zu Alarmen, automatischen Aufnahmen und Ausgaben.
- Vorschau der Verteilung einer Meldergruppe ohne Schaltaktionen oder Nachrichtenversand.

## Voraussetzungen

- Home Assistant mit installierter HACS-Erweiterung für die Installation über HACS.
- Melder und Taster sind bereits über ihre jeweilige Integration in Home Assistant eingerichtet, beispielsweise MQTT oder Zigbee.
- Für Handy-Nachrichten: eingerichtete Home-Assistant-Companion-App oder Pushover-Integration.
- Für Browser-Pop-ups: eingerichtetes Browser Mod und ein verbundenes Dashboard auf dem Zielgerät. Fully Kiosk kann dieses Dashboard anzeigen.

Alarm Management verwendet die in HA vorhandenen Entitäten und Dienste. Die Integration richtet weder die MQTT-Verbindung noch das Zigbee-Netzwerk oder die Herstelleranbindung ein.

## Installation über HACS

1. In HACS das Menü **Benutzerdefinierte Repositories** öffnen.
2. `https://github.com/pherrmann31/alarm-management` hinzufügen und den Typ **Integration** wählen. Ist das Repository bereits vorhanden, diesen Schritt überspringen.
3. **Alarm Management** in HACS herunterladen und die gewünschte veröffentlichte Version auswählen.
4. Home Assistant vollständig neu starten.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Alarm Management** suchen und die Einrichtung abschließen.

Die Integrationsoptionen erreichst du anschließend über das Zahnrad beim Integrationseintrag.

Weitere Hinweise zum Hinzufügen eigener Repositories stehen in der [HACS-Dokumentation](https://www.hacs.xyz/docs/faq/custom_repositories/).

## Geführter Einrichtungsassistent (ab v1.2)

In der Konfigurationsübersicht **Assistenten & Gruppen → Einrichtungsassistent starten** öffnen. Die Übersicht ist in dieser Reihenfolge angeordnet: Status & Überblick, Assistenten & Gruppen, Eingangsquellen, Ausgänge verwalten, Regelverwaltung und Benachrichtigungen.

Der Assistent führt durch **Eingangsquellen → Ausgänge → Regeln → Benachrichtigungen**. Der erste Eingabedialog jeder neuen Stufe öffnet sich direkt. Nach einem Eintrag kannst du weitere anlegen, weitergehen oder zurückwechseln. Vorhandene Quellen und Ziele stehen in den Auswahlfeldern ebenfalls zur Verfügung.

Neue Eingänge und Schaltausgänge sind bei neuen Regeln vorausgewählt und können geändert werden. Nach dem Anlegen von Benachrichtigungen wählst du, welche Regeln sie anfordern sollen; neue Regeln sind dafür vorausgewählt. Eine bewusst leere Auswahl lässt die Benachrichtigungen ohne Zuordnung.

Vor dem Abschluss zeigt eine Zusammenfassung die neuen Quellen, Ausgänge und Regelzuordnungen. Bis dahin bleibt alles ein Entwurf. **Speichern & zur Übersicht** übernimmt die Konfiguration, lädt die Integration einmal neu und öffnet die Konfigurationsübersicht mit einer Rückmeldung. Aktive Eingänge können danach unmittelbar reale Alarmziele anfordern. **Entwurf verwerfen** oder Schließen vor dem Speichern übernimmt keine Änderungen.

Wenn sich die Konfiguration währenddessen anderswo ändert, etwa durch automatische Melderaufnahme, wird der Abschluss mit einem Konflikthinweis abgebrochen, damit keine neueren Einstellungen überschrieben werden. Wenn das Neuladen scheitert, bleiben die gespeicherten Einstellungen erhalten; die Übersicht verweist auf das HA-Protokoll.

Die einzelnen Verwaltungspunkte und die automatische Melderaufnahme bleiben unabhängig vom Assistenten nutzbar.

## Erste Einrichtung

### 1. Alarmziele vorbereiten

Unter **Ausgänge verwalten** die gewünschten Schalt- oder Textausgänge anlegen. Unter **Benachrichtigungen** Handys oder Browser auswählen und Nachrichten konfigurieren.

| Ausgabe | Unterstützte Ziele bzw. Verhalten |
| --- | --- |
| Schaltausgang | `switch`, `light`, `siren` und `input_boolean`; EIN/AUS je Alarmzustand |
| Kurztext | `text` oder `input_text`; maximal 14 Byte im gewählten Zeichensatz |
| Langtext | `text` oder `input_text`; die Längengrenze des Ziels gilt zusätzlich |
| Benachrichtigung | Ausgewählte HA-App- oder Pushover-Empfänger |
| Pop-up Nachricht Browser | Ausgewählte Browser-Mod-Geräte; bei aktiven Alarmen mit Quittierungsfunktion |

Optional unter **Assistenten & Gruppen** Ausgabe- oder Benachrichtigungsgruppen bilden. Nachrichten behalten dabei ihre eigenen Empfänger und Texte.

### 2. Rauchmelder automatisch aufnehmen

Unter **Assistenten & Gruppen → Rauchmelder automatisch aufnehmen** die gefundenen Melder prüfen, Alarmziele auswählen und die Aufnahme aktivieren.

Dabei wird die Regel **„Feueralarm – alle Rauchmelder“** angelegt beziehungsweise aktualisiert. Sie gilt anschließend auch für neu aufgenommene passende Melder.

- Neue automatische Quellen landen in **„Rauchmelder – Standard“**.
- **„Alle Rauchmelder“** enthält die erkannten Rauchalarmquellen unabhängig von ihrer Raumgruppe.
- Neue passende Entitäten werden während des Betriebs aufgenommen. Ein vollständiger HA-Neustart ist dafür nicht erforderlich.
- Bereits aktive neu aufgenommene Rauchmelder werden ausgewertet und können die konfigurierten Alarmziele anfordern.

**X-Sense über MQTT:** Der eigentliche Rauchalarm muss als `binary_sensor` mit Geräteklasse `smoke` in HA vorhanden sein. In den Entitätseinstellungen entspricht das **„Anzeigen als: Rauch“**. Eine Entität namens „Battery Status“ mit Geräteklasse Batterie ist kein Rauchalarmeingang – auch wenn das Gerät „Smoke Alarm“ heißt.

### 3. Raumgruppen anlegen

Meldergruppen wie **Erdgeschoss** und **Obergeschoss** anlegen und Quellen über **Melder verschieben** zuordnen. Diese manuellen Zuordnungen bleiben erhalten. Neue Geräte landen weiterhin in der Standardgruppe.

Für die allgemeine Feueralarmregel **„Alle Rauchmelder“** verwenden. So bleibt die allgemeine Alarmierung auch nach einem Gruppenwechsel wirksam. Zusätzliche Regeln können gezielt nur eine Raumgruppe auswerten.

### 4. Hausalarmtaster einbinden

Taster können einzeln als Eingangsquelle oder über **Hausalarmtaster automatisch aufnehmen** eingebunden werden.

Für die automatische Aufnahme ein eindeutiges Namensmuster, beispielsweise `event.hausalarm_*`, oder eine HA-Label-ID festlegen. Sind beide Kriterien gesetzt, müssen beide passen. Anschließend den Auslösewert und die Alarmziele auswählen.

- Bei Zustandsquellen den Rohzustand verwenden, beispielsweise `on`.
- Bei `event`-Entitäten einen tatsächlich angebotenen Ereignistyp verwenden, beispielsweise `single`. Die Bezeichnung hängt vom Gerät ab.
- Neue automatische Taster landen in **„Hausalarm – Standard“**. Die automatisch eingerichtete Regel verwendet **„Alle Hausalarmtaster“**.
- Alte Ereigniszeitstempel werden beim Neustart nicht erneut als Tastendruck ausgelöst.

Pro Einrichtung steht derzeit eine automatische Tastervorlage zur Verfügung. Unterschiedliche Tastentypen können zusätzlich einzeln konfiguriert werden. Reine ZHA-Busereignisse oder unverarbeitete MQTT-Nachrichten benötigen eine passende HA-Entität als Eingang.

### 5. Regeln und Verteilung prüfen

In der **Regelverwaltung** Einzelquellen oder Gruppen auswählen, Bedingungen festlegen und Alarmziele zuordnen. Die Gruppenbedingung und die Regelbedingung werden getrennt ausgewertet.

**Verteilung prüfen** berechnet einen hypothetischen Alarm aller aktivierten Mitglieder der gewählten Gruppe. Die Vorschau zeigt Regeln und Ausgabeanforderungen. Sie versendet keine Nachrichten und bestätigt keine Erreichbarkeit oder Zustellung.

## Nachrichtentexte

Texte können folgende Platzhalter enthalten:

| Platzhalter | Inhalt |
| --- | --- |
| `{regel}` | Ausgelöste Regeln |
| `{quelle}` | Auslösende Melder |
| `{bereich}` | Zugeordnete Bereiche |
| `{alarmtyp}` | Alarmtyp, beispielsweise Feuer |
| `{status}` | Aktiv, quittiert oder Ruhezustand |

Beispiel: **`{alarmtyp}: {quelle} – {bereich}`**

Für Alarm, Quittierung und Ruhe/Reset können unterschiedliche Werte hinterlegt werden. Bei Benachrichtigungen bedeutet ein leerer normaler Zustandstext, dass in diesem Zustand keine Nachricht angefordert wird; Fehlermeldungen bei blockiertem Reset und Browser-Quittierungsrückmeldungen werden gesondert behandelt. Texte sind Platzhaltertexte, keine ausführbaren HA-Templates. Zielgrenzen gelten auch nach dem Einsetzen der Platzhalter.

## Alarm, Quittierung und Reset

- **Alarm:** Ein passender Eingang löst eine Regel aus. Der Vorfall bleibt gespeichert, auch wenn die Ursache anschließend wieder verschwindet.
- **Quittierung:** Bestätigt die Kenntnisnahme. Sie beseitigt keine weiterhin aktive Ursache. Ausgänge verwenden ihre konfigurierten Quittierungswerte.
- **Reset:** Setzt zurücksetzbare Vorfälle zurück. Aktive oder für einen vorhandenen Alarm unklare Ursachen können den Reset blockieren; die Integration nennt den Grund.

Mehrere Melder derselben Regel ergänzen deren Vorfall. Unterschiedliche Regeln bleiben getrennte Vorfälle. Ein gemeinsam verwendeter Schaltausgang bleibt EIN, solange mindestens eine zugeordnete Regel EIN anfordert. Regelprioritäten von 0 bis 5 bestimmen die Reihenfolge gemeinsamer Texte; sie unterdrücken keine anderen Alarme.

## Updates und Fehlerbehebung

Vor einem Update ein vollständiges HA-Backup einschließlich Konfiguration und `.storage` erstellen. Das Update über HACS installieren und HA anschließend vollständig neu starten. Die vorhandene Integration weiterverwenden.

**Bei einer unerwartet alten Versionsanzeige:** Die heruntergeladene Version in HACS und den Wert `version` in `/config/custom_components/alarm_management/manifest.json` vergleichen. Nach dem Neustart muss der geladene Stand zur installierten Version passen. Ein alter Geräteeintrag allein bestätigt die geladene Code-Version nicht.

**Bei einem Einrichtungsfehler:** Die genaue Meldung und den zugehörigen Eintrag im HA-Protokoll prüfen. Ab v1.1 nennt die Meldung den betroffenen Teil, etwa Gruppenkonfiguration, Ausgänge oder gespeicherte Alarmvorfälle. Für eine Fehlermeldung auf GitHub HA-Version, Integrationsversion und Schritte zur Reproduktion angeben; persönliche Daten vorher entfernen.

Gespeicherte Alarmdaten nicht von Hand löschen. Ein Rückwechsel auf ältere Versionen kann ein Wiederherstellen des vorherigen vollständigen Backups erfordern, da ältere Versionen neuere Gruppen- und Benachrichtigungsdaten nicht verstehen.

## Entwicklungsstand und Grenzen

Für v1.2.0 wurden **247 automatisierte Offline-Tests** sowie Syntax und Paketstruktur geprüft. Die HA-Anbindung wird dabei mit Testdoubles geprüft. Das ersetzt keine Abnahme im laufenden HA mit den eigenen Meldern, Sirenen, Handys und Tablets. Einzelheiten stehen im [Prüfbericht](VALIDATION.md).

Aktuelle Grenzen:

- Gruppen sind nicht verschachtelt. Raumgruppen werden manuell verwaltet; eine dynamische Zuordnung nach HA-Bereich oder Etage ist noch nicht enthalten.
- Mehrere automatische Tastervorlagen und ein vollständiges Protokoll sämtlicher manueller Gruppenänderungen stehen noch aus.
- Benachrichtigungsgruppen bündeln konfigurierte Nachrichtendefinitionen. Zwei unterschiedliche Definitionen an dasselbe Handy können zwei Nachrichten erzeugen.
- Der Versandstatus bestätigt die Verarbeitung des HA-Serviceaufrufs; er bestätigt keine Anzeige auf dem Endgerät.
- Browser-Pop-ups benötigen einen verbundenen Browser. Ein systemweites Tablet-Overlay oder automatisches Aufwecken ist nicht enthalten.
- Zu lange oder für das Ziel ungeeignete Texte erzeugen einen sichtbaren Ausgabefehler.

**Betriebshinweis:** Aktivierte Ausgänge führen reale Aktionen aus. Die eigenständige Alarmfunktion der Rauchmelder muss unabhängig von Home Assistant erhalten bleiben. Erst die Verteilungsvorschau nutzen und anschließend die tatsächlichen Alarmziele kontrolliert testen.
