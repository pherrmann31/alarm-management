# Alarm Management v0.8.0 — Push und Tablet-Overlay

Für Home Assistant OS / Core 2026.10.4. Eingänge sammeln Signale, Regeln werten sie aus,
Ausgänge verteilen die passenden Zustände und Nachrichten. Diese Version ergänzt echte
Benachrichtigungen neben den bisherigen Schalt- und Textausgängen.

## Neu

- Ausgang **Push-Nachricht** mit Mehrfachauswahl vorhandener HA-App-Ziele.
- Ausgang **Tablet-Overlay** mit Mehrfachauswahl registrierter Browser-Mod-Geräte.
- Titel und Nachricht je Ausgang frei anpassbar, mit den bekannten Platzhaltern
  `{regel}`, `{quelle}`, `{bereich}`, `{alarmtyp}`, `{status}`.
- Optional eigene Nachrichten nach Quittierung und Reset; standardmäßig leer.
- Bis zu 20 Empfänger je Nachrichtenausgang. Dieselbe Ausgangsdefinition kann wie bisher
  mehreren Regeln zugeordnet werden; ihre aktuellen Alarme werden zusammengefasst.
- Pushover über vorhandene notify.pushover-/notify.pushover_*-Aktionen; optionale
  Gerätenamen und Priorität -2 bis 1. Keine API-Schlüssel in dieser Integration.
- Persistenter Versandnachweis je Empfänger und Alarmvorkommen, Fehler im Ausgabeverlauf
  und in recipient_status der Ausgangsanzeige.

## GitHub/HACS-Update

Das Repository ist https://github.com/pherrmann31/alarm-management.
Neue Versionen werden erst nach bewusstem Veröffentlichen eines passenden Releases
in HACS angeboten. Ein neuer Commit auf einem Entwicklungszweig ist noch kein Release.

Vor Update vollständiges HA-Backup erstellen und Testalarme normalisieren.
Nach Installation von v0.8.0 HA vollständig neu starten, bestehende Integration behalten.
Eingänge, Regeln, IDs und vorhandene Ausgangseinstellungen werden übernommen.
Alte Ausgangsoptionen Version 1 werden verlustfrei auf Version 2 ergänzt; Store-Schema
bleibt 5. Neue Empfängernachweise nutzen den vorhandenen atomaren Store. Für Downgrade
auf v0.7 das vorherige vollständige Backup wiederherstellen.
Aktive gespeicherte Alarme können nach Zuordnung neuer Nachrichtenausgänge sofort senden.

## Handy-Push einrichten

1. Die HA-App auf dem Handy anmelden und Benachrichtigungen im Betriebssystem zulassen.
2. Unter Alarm Management → Konfigurieren → Ausgänge → Hinzufügen **Push-Nachricht** wählen.
   Das Schalt-/Text-Zielfeld im ersten Schritt leer lassen.
3. Unter **Geräte & Nachricht** ein oder mehrere Handys auswählen und den Titel anpassen.
   Native HA-App-Entitäten erscheinen bevorzugt mit Namen. Ältere mobile_app-Aktionen
   dienen als Fallback. Nicht zwei Darstellungen desselben Handys auswählen.
4. Unter **Bei Alarm** die Nachricht eingeben, z. B.:

   `{alarmtyp}: {regel}`

   `Quelle: {quelle}`

   `Bereich: {bereich}`

5. Quittierungs-/Ruhemeldungen nur bei Bedarf füllen. Leer bedeutet: nichts senden.
6. Speichern und den neuen Ausgang in der gewünschten Regel unter **Dann …** zuordnen.

Titel höchstens 80, Nachricht höchstens 1024 Zeichen nach Platzhalterersetzung.
Zu lange Nachrichten werden als Fehler angezeigt und nicht still gekürzt.
Nur normale Textnachrichten; keine App-Steuerbefehle, Bilder, Aktionsknöpfe oder
iOS-/Android-spezifischen Critical-Alert-Parameter in dieser Version.
Umbenannte App-Entitäten bei Bedarf in der Geräteauswahl neu auswählen.

## Tablet-Overlay einrichten

1. Das HA-Dashboard im Fully Kiosk Browser des Tablets öffnen. Browser Mod muss
   genau in diesem Browser registriert und mit HA verbunden sein.
2. Dem Browser-Mod-Gerät in HA einen erkennbaren Namen geben, z. B. Flur Tablet.
3. Ausgang **Tablet-Overlay** anlegen und im zweiten Schritt gezielt die gewünschten
   Browser-Mod-Geräte auswählen. Keine Browser-ID abtippen und keine leere Broadcast-Auswahl.
4. Titel und Nachricht einstellen, speichern und der Regel zuordnen.
5. Testalarm auslösen und kontrollieren, dass das Popup auf dem richtigen Tablet erscheint.

Das Overlay ist ein Browser-Mod-Popup über dem geöffneten Dashboard. Fully Kiosk muss
dafür nicht zusätzlich per REST angesprochen werden. Ein ausgeschalteter Bildschirm wird
nicht automatisch aufgeweckt; außerhalb des verbundenen Dashboards gibt es kein
systemweites Android-Overlay und keine garantierte spätere Zustellung.
HTML aus eingegebenen Texten wird als Text dargestellt. Popup schließen quittiert keinen
Alarm. Quittieren/Reset bleiben Aktionen der Alarmverwaltung. Popups werden nicht automatisch
beim Reset geschlossen; sie bleiben bis zum Schließen oder bis zur nächsten Popup-Anforderung.
Andere Browser-Mod-Automationen können das Popup ersetzen.

## Pushover

Vorhandene Pushover-Integration in HA verwenden. In der Push-Geräteauswahl sind
notify.pushover und notify.pushover_*-Aktionen auswählbar. Anders benannte Pushover-Aktionen
werden in dieser Version nicht automatisch erkannt.

HA-App und Browser Mod bieten echte Auswahl vorhandener Ziele. Pushover-Kontogeräte
sind keine HA-Geräte: deren Namen im optionalen Pushover-Feld exakt, mit Kommas ohne
Leerzeichen eintragen. Leer sendet an alle Geräte des ausgewählten Pushover-Kontos.
Fehlerhafte Gerätenamen können von Pushover anders behandelt werden als erwartet;
die tatsächlichen Empfänger vor produktivem Einsatz mit einer Testnachricht prüfen.
Pushover-spezifische Gerätenamen/Priorität nur verwenden, wenn ein Pushover-Ziel gewählt ist.
Notfallpriorität 2 mit Dauerwiederholung und Quittierungsbelegen ist noch nicht enthalten.

## Versand, Wiederholungen und Neustart

Vor jedem Empfängeraufruf wird eine Absicht atomar gespeichert. Derselbe Empfänger wird
für denselben Alarm, Meldungsinhalt und Zustand nach erfolgreicher HA-Übergabe nicht bei
jeder Auswertung oder beim Neuladen erneut angesprochen. Ein neuer Alarm nach Reset
erzeugt ein neues Vorkommen. Weitere Quellen/Regeln oder geänderte Meldungsinhalte können
eine neue zusammengefasste Nachricht auslösen. Änderungen eines anderen Empfängers
allein wiederholen erfolgreich bearbeitete Ziele nicht.

Einzelne Empfängerfehler blockieren die anderen nicht. Nachrichten werden nach Fehlern
oder einem unklaren Versand nicht automatisch wiederholt. **Ausgaben erneut versuchen**
fordert nur fehlgeschlagene/unklare Ziele der aktuellen Meldung neu an; bereits erfolgreich
an HA übergebene Empfänger werden ausgelassen. Bei Timeout oder Absturz zwischen Aufruf
und Ergebnisspeicherung kann dieser bewusste erneute Versuch dennoch eine doppelte
Meldung erzeugen. Es gibt keine garantierte Exactly-once-Zustellung.

Nach einem Neustart bleibt eine gespeicherte, aber nicht abgeschlossene Versandabsicht
sichtbar unklar/fehlerhaft, statt unbemerkt erneut gesendet zu werden. Nicht begonnene
Empfänger dürfen noch bearbeitet werden. Beim HA-Stopp werden keine neuen Aufrufe
begonnen. Ein schon laufender Aufruf lässt sich beim Reset nicht zurückholen; verbleibende
veraltete Empfänger werden übersprungen. Keine automatische Ruhemeldung bei Installation.

**An HA übergeben** bedeutet nur, dass die HA-Aktion ohne Fehler zurückkam. Es beweist
nicht Empfang, Anzeige oder Lesen auf dem Endgerät. Browser Mod kann einen nicht
verbundenen Browser nicht nachträglich benachrichtigen. Für App/Pushover gelten deren
Netzwerkverbindung, Berechtigungen und Anbieterlimits.

## Abnahme zuerst mit Testhelfern

1. Einen Push-Ausgang für dein Handy und einen Overlay-Ausgang für genau ein Tablet anlegen.
2. Beide einer Testregel zuordnen und mit einem Testhelfer auslösen.
3. Text, Quelle, Bereich und tatsächliche Empfänger kontrollieren.
4. Eingang wieder normal setzen: keine doppelte Alarmmeldung erwarten.
5. Quittieren/Reset mit leeren Meldungen prüfen: keine Nachricht. Danach optionale Texte testen.
6. Zwei Handys wählen, einen Empfänger nicht verfügbar machen und Fehleranzeige/gezielte
   manuelle Wiederholung prüfen. Bereits erfolgreiche Empfänger dürfen nicht erneut senden.
7. Aktiven Alarm neu laden/neustarten: keine unbeabsichtigte Doppelmeldung.
8. Bestehende Schalt- und Textausgänge ebenfalls prüfen.

193 Offline-Tests bestanden; kein echter HA-/Browser-/Handy-/Pushover-Test hier ausgeführt.
Die Geräteabnahme erfolgt in deiner Installation. Details: [VALIDATION.md](VALIDATION.md).

## Noch offen

Alarmprioritäten und Eskalationsketten, zeitabhängige Empfänger, Einzelalarm-Quittierung,
Aktionsknöpfe in Pushmeldungen, bestätigte Zustellung, Pushover-Notfallwiederholung,
automatisches Wecken des Tablets und ein gezieltes automatisches Schließen eigener Popups.

## Quellen

- [HA-App-Benachrichtigungen](https://companion.home-assistant.io/docs/notifications/notifications-basic/)
- [Pushover in HA](https://www.home-assistant.io/integrations/pushover/)
- [Browser-Mod-Aktionen und Zielauswahl](https://github.com/thomasloven/hass-browser_mod/blob/master/documentation/services.md)
- [Core 2026.10.4 MobileAppNotifyEntity](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/mobile_app/notify.py)

## Bisherige Geräteausgaben und Sicherheits-/Testhinweise

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

Siehe `VALIDATION.md`. Alle Prüfungen hier verwenden eine lokale Python-Umgebung und
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
