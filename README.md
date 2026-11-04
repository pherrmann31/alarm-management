<<<<<<< Updated upstream
# Alarm Management v0.7.0 — übersichtliche Konfiguration

Für Home Assistant OS / Core 2026.10.4. Dieses Update überarbeitet die normale
HA-Konfiguration und die Darstellung der Entitäten. Echte Geräteausgaben aus v0.6
bleiben aktiv. Alarm-, Regel-, Speicher- und Ausführungslogik wurden nicht verändert.

## Installation über HACS

Dieses öffentliche Repository lässt sich als benutzerdefiniertes HACS-Repository
vom Typ **Integration** hinzufügen: https://github.com/pherrmann31/alarm-management

Anschließend in HACS **Alarm Management** herunterladen und Home Assistant neu starten.
Bei der erstmaligen Einrichtung zusätzlich unter Geräte & Dienste die Integration hinzufügen.
Bei einer bereits vorhandenen manuellen Installation den bestehenden Eintrag behalten.
Ausführliche Erstveröffentlichung und Übernahme: [GITHUB-ANLEITUNG.md](GITHUB-ANLEITUNG.md).
Der Code steuert konfigurierte Ausgänge tatsächlich; vor Übernahme Backup erstellen.

## Manuelles Update von v0.6.0

1. HA-Backup erstellen. Testeingänge ausschalten und Testalarme zurücksetzen.
   Bestehende aktive Anforderungen können nach einem Neustart weiter ausgeführt werden.
2. `alarm_management-v0.7.0.zip` am PC entpacken. Den enthaltenen Ordner
   `alarm_management` nach `/config/custom_components/` kopieren und vorhandene Dateien
   ersetzen/zusammenführen. Ziel: `/config/custom_components/alarm_management/manifest.json`.
   Es darf kein weiterer Ordner `alarm_management` darunter entstehen.
3. **Deine vorhandenen PNGs unter `brand/` behalten.** Den Ordner zusammenführen,
   nicht erst löschen. Das Paket enthält dort nur die Anleitung und überschreibt keine PNGs.
4. Home Assistant vollständig neu starten, Browser mit Strg+F5 aktualisieren.
5. Unter Einstellungen → Geräte & Dienste → Alarm Management die Version 0.7.0 prüfen
   und über das Zahnrad die Konfiguration öffnen. Die vorhandene Integration behalten.

Eingänge, Regeln, Ausgänge, Zuordnungen, gespeicherte Alarme und Entitäts-IDs bleiben
erhalten. Store-Schema bleibt 5; es gibt gegenüber v0.6 keine neue Datenmigration.
V0.6 unterstützt weiterhin Migrationen aus älteren Store-Schemata 1–4. Bei einem
Update direkt aus v0.5 oder älter deshalb auch den Abschnitt zu echten Ausgaben lesen.

## Was jetzt übersichtlicher ist

- Hauptmenü mit aktuellem Alarmzustand, Anzahl der Alarme sowie Eingängen, Regeln und Ausgängen.
- **Status & Überblick:** Momentaufnahme mit Alarmquellen, ausgelösten Regeln und Fehlerzahlen.
- Kürzere Dialogtexte, Erläuterungen direkt an den Feldern und beschreibende Menüuntertitel.
- **Regeln:** oben Name/Aktivierung, darunter **Wenn …** mit Eingängen und UND/ODER
  sowie **Dann …** mit Alarmtyp und Ausgangszuordnung.
- **Ausgänge:** oben Name/Ziel/Aktivierung. Werte für **Bei Alarm**, **Nach Quittierung**
  und **In Ruhe / nach Reset** in eigenen Abschnitten. Quittierung und Ruhe sind anfangs
  eingeklappt; beim Kurztext ebenso der Zeichensatz. Ein Fehler öffnet den betroffenen Abschnitt.
- Eingangsübersicht mit Zustand und Bereich; Regelübersicht mit Wenn/Dann und Ausgängen;
  Ausgangsübersicht mit Typ, Ziel, Regelbindung und Ausführungsstatus.
- **Weiter** führt aus den Übersichten zurück ins jeweilige Menü, ohne zu speichern
  oder neu zu laden. Statuswerte sind Momentaufnahmen und werden beim Öffnen ermittelt.
- Mehrere neue Einträge lassen sich wie bisher nacheinander anlegen und gemeinsam speichern.

## Darstellung der Entitäten

Die Geräteseite zeigt die zentralen Anzeigen und Bedienknöpfe im Hauptbereich.
Zähler und Verläufe sind als Diagnose kategorisiert und stehen im HA-Bereich **Diagnose**.
Das beeinflusst auch automatisch erzeugte Dashboard-Ansichten. Vorhandene manuelle
Dashboard-Karten und Automationen behalten ihre Entitäts-IDs.

| Hauptanzeigen | Diagnose |
| --- | --- |
| Alarmstatus mit Zustandssymbol | Ausgelöste Eingänge |
| Alarmquellen, Bereiche, Alarmregeln | Erfüllte Regeln |
| Ausgabestatus und einzelne Ausgangsanzeigen | Alarmverlauf, Ausgabeverlauf |
| Quittieren, Reset, Ausgaben erneut versuchen | |

Einzelne Ausgangsanzeigen heißen standardmäßig `Schalten · Name`, `Kurztext · Name`
oder `Langtext · Name`. Sirenen, Leuchten und Texttypen erhalten passende Symbole,
Ausgabefehler ein Warnsymbol. Eigene Namen und Symbole aus der HA-Entitätsverwaltung
können diese Standardwerte übersteuern. Sie werden absichtlich nicht gelöscht.
Falls ein alter Name bleibt, in der jeweiligen Entität den eigenen Namenswert leeren,
um wieder den Standard zu verwenden; die Entitäts-ID dabei beibehalten.

Es handelt sich um native HA-Dialoge und Kategorien. Kein eigener Dashboard- oder
Frontend-Baustein: Farben, Kartengestaltung, Reihenfolge und der kleine Dienstzeilen-Icon
werden von Home Assistant festgelegt. Das vorhandene große Integrationslogo bleibt erhalten.

## Was gegenüber den bisherigen Plänen umgesetzt ist

Eingänge, bearbeitbare UND/ODER-Regeln, gespeicherte Alarme, Quellen/Bereiche, Quittierung,
Reset, begrenzte Verläufe, frei zugeordnete Schalt-/Textausgänge und echte Ausführung
stammen aus den bisherigen Versionen. V0.7 ergänzt deren Konfiguration und Anzeige.
Es kommen keine neuen Alarmbedingungen oder Geräteaktionen hinzu. Erweiterungen wie
Zeitpläne, Prioritäten und Einzelalarm-Reset bleiben offen; siehe Grenzen am Ende.

## Kurzer Oberflächentest nach dem Update

1. Eingang öffnen: Name, Ziel, Rohwert und Aktivierung müssen stimmen.
2. Regel öffnen: unter Wenn die bisherigen Eingänge/Verknüpfung, unter Dann Alarmtyp
   und Ausgänge prüfen. Ohne Änderung schließen.
3. Ausgang öffnen: alle drei Wertabschnitte aufklappen, beim Kurztext Zeichensatz prüfen.
4. Mit eigenen Testhelfern einen Eingang auslösen. Alarmstatus, Quelle, Bereich,
   Regel und tatsächliche Zielzustände prüfen. Danach quittieren und zurücksetzen.
5. Status-/Listenübersichten öffnen und mit Weiter zurückgehen; dabei dürfen keine
   Optionen gespeichert werden. Diagnosebereich und Ausgangssymbole prüfen.

172 Offline-Tests und Syntax-/Paketprüfung bestanden. Die konkrete Darstellung im
laufenden Home Assistant wurde hier nicht visuell getestet. Der separate Prüfbericht
beschreibt genau die durchgeführten Prüfungen und ihre Grenzen.

## Unterstützte echte Ausgaben

| Ziel | Tatsächliche HA-Aktion |
| --- | --- |
| switch, light, siren, input_boolean | turn_on oder turn_off |
| text, input_text | set_value mit dem vorbereiteten Text |
| Textausgang ohne Ziel | Nur eigene Statusentität aktualisieren |

Es werden ausschließlich konkrete einzelne Zielentitäten angesprochen, keine Bereiche,
Gruppen, beliebigen Dienste, Skripte oder toggle-Befehle. Sirenen verwenden die Standardwerte
ihrer Integration; Ton, Lautstärke und Dauer sind noch nicht konfigurierbar. Ein Gerät, dessen
Aktion zusätzliche Parameter verlangt, kann deshalb einen sichtbaren Fehler liefern.

Eingänge/Regeln/Ausgänge werden wie bisher unter Konfigurieren verwaltet. Pro Ausgang gelten
Werte für Alarm, Quittierung und Ruhe. Gemeinsame Schaltausgänge bleiben EIN, solange eine
beteiligte Regel EIN anfordert. Es gibt weiterhin bis zu zehn Eingänge, 30 Regeln und 20 Ausgänge.
Ein Ausgang pro Ziel verhindert widersprüchliche Definitionen innerhalb dieser Integration.
Andere Automationen, die dasselbe Gerät steuern, werden dadurch nicht koordiniert:
vorzugsweise eigene, eindeutig zugeordnete Alarmziele verwenden.

## Gesendet und bestätigt unterscheiden

Die Ausgangsentität zeigt den Sollwert und in ihren Attributen:

- `delivery_status`: pending, sent, confirmed, failed, mismatch, internal oder idle.
- `delivery_error`: konkrete Fehlermeldung der Ausführung.
- `observed_value`: aktuell von HA gelesener Zielzustand.
- `target_owned`: ob die Integration einen noch zu verwaltenden Befehl für dieses Ziel hat.

„Gesendet“ bedeutet, dass die HA-Aktion zurückgekehrt ist. Erst wenn die Zielentität den
angeforderten Wert meldet, wird „Zustand bestätigt“ gesetzt. Diese Bestätigung ist die
HA-Zustandsmeldung, keine unabhängige elektrische oder physische Prüfung des Aktors.
Der globale Ausgabestatus zeigt Ausgabefehler, Ausgabe läuft, Rückmeldung offen oder Bereit.
Alarmstatus und Ausgabestatus sind getrennt: Ein gespeicherter Alarm kann zurückgesetzt sein,
während ein unerreichbares Gerät seinen Ruhewert noch nicht bestätigt hat.

Das Ausgabeprotokoll zeigt jetzt tatsächliche Ausführungsversuche und Rückmeldungen,
bis zu 100 Einträge. Die frühere Planhistorie bleibt separat im Store erhalten. Die Diagnose
enthält `alarm_session.executions`, `delivery_history`, `output_plan` und `output_history`.
Vor Weitergabe Namen, Bereiche und Texte prüfen.

## Neustart, Quittierung, Reset und Deaktivierung

Beim Start werden aktive Alarme erneut mit ihren Zielzuständen abgeglichen. Bereits passende
Zustände benötigen keinen neuen Geräteaufruf. Ein unbenutztes Ziel ohne Alarm und ohne vorherige
Steuerung durch die Integration wird im Ruhezustand nicht pauschal überschrieben.

War ein Ziel schon vor der ersten Alarmanforderung auf dem passenden Wert, sendet die Integration
keinen redundanten Befehl und beansprucht die fremde Steuerung nicht. Beim späteren Reset wird
dieses Ziel folglich nicht ausgeschaltet. Das ist keine vollständige Mehrfachsteuerungs-Koordination.

Ein durch diese Integration wirklich angesprochener Ausgang übernimmt bei Quittierung seinen
Quittierungswert und bei Reset seinen Ruhewert. Reset ist wie v0.4 gesperrt, solange eine Regel
erfüllt ist oder eine alarmierte Regel unbestimmbar bleibt. Der Geräteaufruf erfolgt nach dem
gespeicherten Zustandswechsel; die Rückmeldung im Ausgabeprotokoll prüfen.

Beim Deaktivieren einer Regel entfällt deren Beitrag; andere Regeln können den Ausgang weiter
anfordern. Beim Deaktivieren eines schon gesteuerten Ausgangs wird dessen Ruhewert angefordert.
Zielwechsel und Entfernen eines noch gesteuerten Ausgangs werden im Dialog gesperrt, bis sein
Ruhewert bestätigt ist. Zuerst normalisieren/zurücksetzen oder deaktivieren und die Bestätigung
abwarten. Ein Ziel ohne Rückmeldung muss gegebenenfalls direkt geprüft und sein Zustand in HA
wiederhergestellt werden, bevor die Zuordnung geändert werden kann.

Entladen, Deaktivieren der gesamten Integration, Entfernen oder HA-Stopp senden keinen
pauschalen AUS-Befehl. Geräte können dann ihren zuletzt erreichten Zustand behalten. Vor dem
Entfernen zuerst Alarme normalisieren und zurücksetzen bzw. Ausgänge deaktivieren und die
Ruhewerte bestätigen lassen. Bereits laufende Aktionen dürfen noch abschließen, neue werden
beim Entladen nicht mehr begonnen. Wiederholungs-Timer werden entfernt.

## Fehler, Zeitgrenzen und Wiederholen

Die Ausführungsabsicht wird gespeichert, bevor ein externer Befehl gesendet wird. Scheitert
dieser Schreibvorgang, erfolgt kein neuer Geräteaufruf. Ergebnisse werden ebenfalls gespeichert;
ein Fehler dabei bleibt als Speicherfehler sichtbar und wird nicht als Erfolg ausgegeben.
Alarm- und Ausführungsdaten werden beim nächsten Schreibversuch zusammengeführt, damit eine
verspätete Wiederholung keine neueren Rückmeldungen überschreibt.

Je Ausgang sind höchstens drei Versuche für denselben aktuellen Befehl vorgesehen, mit mindestens
fünf Sekunden Abstand. Ein HA-Aufruf hat ein Zeitlimit von zehn Sekunden. Höchstens vier
Geräteaufrufe laufen parallel; pro Ausgang werden sie serialisiert. Vor dem Absenden wird ein
wartender Befehl nochmals gegen den aktuellen Sollwert geprüft. Ein bereits begonnener Aufruf
kann beim Reset nicht zurückgeholt werden; anschließend wird der aktuelle Sollwert bearbeitet.

Dienstfehler und bekannte abweichende Zustände führen zu begrenzten Wiederholungen. Wenn HA
den Aufruf akzeptiert hat, aber das Ziel keine Zustandsrückmeldung liefert, bleibt der Status
„Gesendet“; es gibt keine endlosen blinden Wiederholungen. Ein Timeout kann bedeuten, dass das
Gerät den Befehl trotzdem empfangen hat. Absolute EIN/AUS-/Textwerte vermeiden Toggle-Dopplungen,
sind aber bei Geräten mit eigener Zeitsteuerung nicht frei von Nebeneffekten.

Über die Schaltfläche **Ausgaben erneut versuchen** oder `alarm_management.retry_outputs`
beginnst du für aktuelle Anforderungen einen neuen begrenzten Versuchslauf. Nicht angeforderte,
bisher nicht gesteuerte Ruheziele werden dadurch nicht neu überschrieben.

## Texte und der behobene unknown-Fehler

Vorhandene geladene Textziele mit noch unbekanntem Inhalt dürfen beschrieben werden. Fehlende,
tatsächlich nicht verfügbare oder lediglich wiederhergestellte Platzhalter-Entitäten bleiben
gesperrt. Der in v0.5.0 beobachtete Fehler durch einen unbekannten Textinhalt ist behoben.

Kurztext bleibt auf 14 Byte in ASCII (DPT 16.000) oder Latin-1 (16.001) begrenzt, einschließlich
Platzhalterersetzung. Zu lange oder unzulässige Texte werden nicht gesendet und nicht still
gekürzt. Langtext ist intern bis 4096 Zeichen möglich, ein text/input_text-Ziel erlaubt höchstens
255 und eventuell weniger. Zielmindest-/Maximallänge wird vor dem Aufruf geprüft; weitere
geräteseitige Einschränkungen können beim Aufruf einen Fehler liefern.

Platzhalter: {regel}, {quelle}, {bereich}, {alarmtyp}, {status}. Nur einfache Ersetzung, keine
Python-/Jinja-Auswertung. Bei mehreren Alarmen werden Namen zusammengefasst; ein gemeinsamer
Kurztext kann dadurch zu lang werden. Eine Textpriorisierung oder wechselnde Displayseiten
sind noch nicht enthalten. Die eigene Statusentität zeigt bis 255 Zeichen, größere Werte stehen
größenbegrenzt in Attributen und vollständig im Store/der Diagnose.

## Abnahmetest zuerst mit Helfern

1. Vor dem Update alle Testeingänge ausschalten und zurücksetzen.
2. Einen unbenutzten input_boolean als Ziel eines Schaltausgangs auswählen, einen input_text
   als Textziel. Diese Helfer dürfen keine realen Geräteautomationen auslösen.
3. Alarmregel über einen dritten Testhelfer auslösen. Nun müssen der Zielschalter tatsächlich
   EIN und der Texthelfer tatsächlich z. B. Einbruch zeigen. Ausgabeprotokoll prüfen.
4. Quittieren: konfigurierte Quittierungswerte müssen ankommen.
5. Eingang ausschalten, Reset: Ruhewerte prüfen, Status confirmed und target_owned false.
6. Eine aktive Anforderung über Neustart prüfen: gewünschter Zustand muss weiter abgeglichen
   werden, ohne dass bereits passende Ziele unnötig erneut beschrieben werden.
7. Zwei Regeln demselben Ausgang zuordnen und gemeinsame EIN-Anforderung prüfen.
8. Einen Ausgang deaktivieren und kontrollieren, dass sein Ruhewert bestätigt wird.
9. Fehlendes Textziel/zu langen Kurztext prüfen: kein irreführender Erfolgsstatus.
10. Erst nach erfolgreicher Abnahme Zielentitäten einzeln auf die vorgesehenen Geräte umstellen.

Die Aktionen trigger_test, acknowledge und reset bleiben erhalten. Der unabhängige manuelle
Testalarm hat keine Regelbindung und löst deshalb keine regelgebundenen Geräteausgaben aus.

## Integrationssymbol

Eigene PNG-Dateien nach `/config/custom_components/alarm_management/brand/` kopieren:
`icon.png` mit 256 × 256 und `icon@2x.png` mit 512 × 512 Pixeln. Optional dunkle Varianten
`dark_icon.png` und `dark_icon@2x.png` in denselben Größen. Quadratisch, möglichst transparent,
ohne unnötigen Rand. Ein eigenes Motiv ist noch nicht im ZIP enthalten. Die Anleitung liegt
auch im brand-Ordner. Danach HA neu starten und Browser mit Strg+F5 aktualisieren.

## Prüfstand und praktische Grenzen

Siehe `VALIDATION-v0.7.0.md`. Alle Prüfungen hier verwenden eine lokale Python-Umgebung und
ausdrücklich benannte HA-Testdoubles. Kein echter HA-Core-Start, keine UI-/Dateispeichermigration
und keine Hardware wurden hier getestet. „Echte Ausführung implementiert“ ist keine Aussage,
dass dein System damit bereits abgenommen, ausfallsicher oder als Alarmanlage zertifiziert ist.

Es fehlen weiterhin priorisierte Textausgaben, numerische Bedingungen, Zeitpläne, konfigurierbare
Sirenenparameter, Einzelalarm-Reset, Hardware-Watchdog und unabhängige Aktorbestätigung.
Bei HA-/Netzwerk-/Datenträgerausfall können Ausgaben verspätet sein, ausbleiben oder im letzten
Zustand verbleiben. Diese Eigenentwicklung ersetzt keine vorgesehene Brand-/Personenschutzanlage.

Primärquellen:

- [HA-ServiceRegistry.async_call, Core 2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/core.py)
- [HA TextEntity, Core 2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/text/__init__.py)
- [HA-Formulare und Abschnitte](https://contributors.home-assistant.io/core/integrations/flow-steps/)
- [HA-Entitätskategorien](https://contributors.home-assistant.io/core/quality-scale/entity-category/)
- [HA-Integrationsbilder](https://contributors.home-assistant.io/core/integrations/brands/)
- [Lokale Brand-Dateien, Core 2026.10.4](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/brands/__init__.py)

Entwicklertests im separaten Quellpaket: `python -B -m unittest discover -s tests -v`.
=======
# Alarm Management v1.1 – Updateprüfung und Gruppenverwaltung

Version **1.1.0**, Ziel Home Assistant Core 2026.10.4. Reale Geräteaktionen sind aktiviert. Die automatische Aufnahme ist zunächst ausgeschaltet und wird einmal mit passenden Alarmzielen eingerichtet.


## Änderungen in v1.1.0

- Update von v0.9 mit bestehenden Eingängen, Regeln, Ausgängen und Benachrichtigungen ausdrücklich geprüft. Die IDs und Zuordnungen bleiben erhalten.
- Gruppen werden beim Update initialisiert und in den Optionen gespeichert. Ältere unvollständige v1-Gruppenentwürfe erhalten fehlende bekannte Standardfelder und Standardgruppen; vorhandene Einstellungen werden nicht überschrieben.
- Beschädigte Werte oder unbekannte Referenzen werden weiterhin abgelehnt. Die Einrichtung nennt jetzt die betroffene Stufe und die Version, zum Beispiel „Alarm Management 1.1.0: Gruppenkonfiguration …“ oder „gespeicherte Alarmvorfälle …“.
- Kein Zurücksetzen oder Löschen vorhandener Alarmdaten, keine automatische Aufnahme vor ausdrücklicher Aktivierung.

## Wichtig bei angezeigter Version 0.7.0

Wenn HA oben 0.7.0 meldet und der Geräteeintrag 0.9.0, ist alter Integrationscode mit einem gespeicherten neueren Geräteeintrag kombiniert. Das ist kein Beleg, dass v1.0-Code geladen wurde. v0.7 unterstützt das Ausgabeformat der Benachrichtigungen ab v0.8 nicht. Der genaue Fehler im laufenden HA muss bei Bedarf anhand seines Protokolls bestätigt werden.

Das Tag `v1.1.0` muss auf den Commit mit `custom_components/alarm_management/manifest.json` Version `1.1.0` zeigen. Auf GitHub nach dem Release dessen „Source code (zip)“ öffnen und diese Datei prüfen. Der Release-Titel allein bestimmt den enthaltenen Code nicht. In HACS ausdrücklich `v1.1.0` installieren und anschließend HA vollständig neu starten. Danach müssen sowohl Manifest als auch geladene Integration 1.1.0 melden. Bestehende Tags nicht wiederverwenden oder verschieben.

Wenn der Fehler auch mit geladenem v1.1.0 fortbesteht, die neue genaue Fehlermeldung und den zugehörigen HA-Protokolleintrag prüfen. Keine Dateien in `.storage` von Hand bearbeiten und die Integration nicht löschen.

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

GitHub-Paket an der Repository-Wurzel entpacken: Dort liegen `hacs.json`, README und `custom_components/alarm_management/`. Den inneren Integrationsordner nicht direkt an die Repository-Wurzel kopieren. Änderungen auf einem eigenen Entwicklungszweig committen und veröffentlichen. GitHub-Release mit Tag `v1.1.0` erstellen, Ziel ist dieser Zweig. Als regulären Release veröffentlichen, damit HACS diese Version standardmäßig anbietet. Kein bestehendes Tag verschieben.

In HACS Alarm Management öffnen, Informationen aktualisieren und bei „Erneut herunterladen“ diese Testversion auswählen; gegebenenfalls Beta-Versionen anzeigen. Nach dem Dateiupdate HA neu starten. Danach zeigt die Integration 1.1.0 an.

## Praktische Abnahme

1. Tatsächliche X-Sense-Rauchalarm-Entität prüfen: `smoke`; die Batterie-Entität darf nicht aufgenommen werden.
2. Aufnahme aktivieren, Testmelder kontrolliert auslösen, Quelle und Bereich prüfen sowie Sirene/Display/Handy testen.
3. Melder nach EG verschieben; allgemeine Feueralarmregel muss weiterhin reagieren.
4. Weiteren passenden Melder hinzufügen; er muss automatisch in Standard erscheinen und dieselben Alarmziele verwenden.
5. Zwei Melder und zwei Regeln gleichzeitig testen: Quittierung und Reset eines Zusammenhangs dürfen andere Alarmanforderungen nicht verlieren.
6. Tasterereignis testen, anschließend Integration und HA neu starten: kein erneuter Alarm durch den alten Ereigniszeitstempel.
7. Nichterreichbaren Melder und fehlgeschlagene Ausgabe prüfen; beide müssen verständlich sichtbar sein.

Die eigenständige Alarmfunktion der Rauchmelder muss unabhängig von Home Assistant erhalten bleiben. Dieser Testrelease wurde nicht mit deinen physischen Geräten oder einem laufenden HA-Core geprüft.
>>>>>>> Stashed changes
