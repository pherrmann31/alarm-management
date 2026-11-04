# Alarm Management v0.9.0 — eigene Benachrichtigungsverwaltung

Für Home Assistant OS / Core 2026.10.4. Eingänge sammeln Signale, Regeln werten sie aus,
Ausgänge und Benachrichtigungen verteilen die passenden Zustände und Nachrichten.
Bestehende Einstellungen, IDs und Regelzuordnungen bleiben erhalten.

## Neue Navigation

Das Hauptmenü enthält Status & Überblick sowie:

- **Eingangsquellen** — vorhandene HA-Signale und ihre Auslösezustände.
- **Regelverwaltung** — Eingangsbedingung, Alarmtyp sowie getrennte Auswahl für
  Schalt-/Textausgänge und Benachrichtigungen.
- **Ausgänge verwalten** — ausschließlich Schalten, Kurztext und Langtext.
- **Benachrichtigungen** — die Typen **Benachrichtigung** (HA-App/Pushover)
  und **Pop-up Nachricht Browser** (Browser Mod).

Bei Benachrichtigungen erscheint im ersten Schritt kein Zielentitätsfeld mehr.
Empfänger, Titel und Nachricht werden im folgenden Schritt gewählt. Vorhandene
Push-/Overlay-Einträge sind automatisch hier sichtbar; keine Neuanlage erforderlich.
Ausgänge und Benachrichtigungen teilen sich weiterhin das Limit von insgesamt 20 Einträgen.

Die Regelauswahl zeigt den Namen, bei Bedarf mit „deaktiviert“. Die störenden UND/ODER-
Zusätze entfallen. Die Bedingung bleibt einstellbar: mindestens ein Eingang oder alle
gewählten Eingänge gleichzeitig. Die Auswertungslogik wurde dadurch nicht entfernt.

## Texte für Quittierung und Reset

Neue Benachrichtigungen sind vorbelegt mit:

- Quittierung: `Alarm quittiert: {regel}` sowie `Quelle: {quelle}`.
- Erfolgreicher Reset: `Reset erfolgreich. Alarmverwaltung ist bereit.`

Beide Texte sind frei änderbar. Bestehende eigene Texte und absichtlich leere Werte
werden beim Update nicht überschrieben. Bei vorhandenen Einträgen die Texte bei Bedarf
unter Benachrichtigungen → Bearbeiten eintragen. Leere normale Zustandsmeldungen bleiben
stumm; Rückmeldungen nach einer Pop-up-Quittierung und Resetfehler werden dennoch angezeigt.
Keine automatische Ruhemeldung bei erstmaliger Einrichtung.

## Abgelehnten Reset melden

Ein Reset bei weiterhin ausgelöster oder unklarer Regel wird weiterhin abgelehnt.
Neu ist die Nachricht an die Benachrichtigungen, die den blockierenden Regeln zugeordnet
sind. Der Text nennt Regel und Grund, bei passenden Quellen auch deren Namen, z. B.:

`Reset nicht möglich. Einzelregel: Alarmanlage: weiterhin ausgelöst: Haustür.`

Bei unklarem Eingang weist die Meldung auf den nicht eindeutigen Eingangsstatus hin.
Mehrere Gründe werden übersichtlich zusammengefasst; vollständige Daten bleiben im
Alarmverlauf/der Diagnose. Unbeteiligte Empfänger werden nicht zusätzlich angeschrieben.
Alarm und Schaltausgänge werden durch den abgelehnten Reset nicht zurückgesetzt.
Dieselbe Warnung wird bei unveränderter Auswertung nicht fortlaufend neu gesendet;
ein erneuter bewusster Resetversuch kann eine neue Rückmeldung erzeugen.

## Quittieren direkt im Browser-Pop-up

Aktive Pop-up-Nachrichten erhalten **Quittieren** und **Schließen**.
Schließen ist nur das Schließen der Anzeige. Quittieren ruft die Alarmverwaltung auf.
Der Knopf bleibt während der Bearbeitung im Pop-up; nach erfolgreicher Speicherung
erscheint der konfigurierte Quittierungstext. Ist dieser leer, erscheint stattdessen
„Quittierung übernommen.“ Die erfolgreiche Quittierung wird im Alarmverlauf gespeichert.
Die Rückmeldung geht an die Browser-Geräte dieser Benachrichtigung.

Quittiert werden nur die Alarmvorkommen, die zu dieser Pop-up-Benachrichtigung gehören.
Andere Regeln und der unabhängige manuelle Testalarm bleiben unverändert. Der vorhandene
allgemeine Quittieren-Knopf in HA quittiert weiterhin alle gespeicherten Alarme.
Passende Quittierungswerte der betroffenen Schalt-/Textausgänge werden wie bisher angefordert.

Eine alte Pop-up-Meldung darf keine nach Reset neu entstandenen Alarme, neu hinzugekommene
Regeln oder zusätzliche Quellen unbemerkt quittieren. In diesem Fall lehnt der Server
die Aktion ab und meldet „Quittierung nicht übernommen …“. Der aktuelle Alarm bleibt aktiv.
Ein Speicherfehler erzeugt keine erfolgreiche Bestätigung. Ohne Browser-Verbindung kann
die Rückmeldung nicht garantiert angezeigt werden; der tatsächliche HA-Zustand ist maßgeblich.

Die Aktion `alarm_management.acknowledge_popup` verwendet output_id und einen
Vorkommensnachweis aus der angezeigten Meldung. Diese Angaben werden automatisch erzeugt;
keine Schlüssel oder Browser-IDs müssen in ein Pop-up-Template eingetragen werden.
Browser Mod muss Aktionsknöpfe und deren right_button_action unterstützen.

## Update über HACS

Repository: https://github.com/pherrmann31/alarm-management.
Entwicklungszweig für diese Version: codex/v0.9-notification-management.
Erst ein neues Release mit Tag v0.9.0 und diesem Zweig als Target macht die Version als
Release in HACS auswählbar. Als Testversion veröffentlichen und bewusst installieren.

Vorher vollständiges HA-Backup erstellen, Testeingänge normalisieren und Testalarme
zurücksetzen, soweit das mit der installierten Version sicher möglich ist. Nach Download
HA vollständig neu starten. Bestehende Integration behalten und alte Konfigurationsdialoge
schließen. Erst nach Anzeige von 0.9.0 erneut konfigurieren.

Die Korrekturen für Formular-Standardwerte und den Hänger beim Neuladen aus v0.8.1/v0.8.2
sind enthalten. Store bleibt Schema 5, Ausgangsoptionen Version 2. Es gibt keine neue
Dateimigration. Neue Protokollereignisse können von alten Versionen nicht gelesen werden;
für einen Downgrade das vorherige vollständige Backup wiederherstellen.

## Abnahme mit Testhelfern

1. Navigation prüfen: Schalt-/Textziele nur unter Ausgänge, Push/Pop-ups unter Benachrichtigungen.
2. Bestehende Regel öffnen: bisherige Schalt-/Textausgänge und Benachrichtigungen müssen in
   ihren getrennten Listen angehakt bleiben. Namen und Eingangsbedingung kontrollieren.
3. Einer Testregel eine Handy-Benachrichtigung und eine Browser-Pop-up-Nachricht zuordnen.
4. Auslösen und Reset bei noch aktivem Eingang drücken: Resetfehler muss am Handy und
   im Pop-up erscheinen, Alarm/Schaltanforderung müssen bestehen bleiben.
5. Im aktiven Pop-up Quittieren drücken: Alarmstatus, Ausgangswerte und Rückmeldung prüfen.
   Eine gleichzeitig aktive, unzugeordnete Regel muss weiterhin aktiv bleiben.
6. Eingang normal setzen und erfolgreich zurücksetzen: den konfigurierten Resettext prüfen.
7. Neue Auslösung erzeugen und einen alten Pop-up-Aufruf absetzen: neue Auslösung darf
   nicht quittiert werden. Dafür keinen produktiven Alarm verwenden.
8. Neu laden/neustarten und Speicherfehler-Verhalten nur mit Testhelfern prüfen.

218 Offline-Tests bestanden, einschließlich der bisherigen 201 Regressionen und
17 neuer Prüfungen für Navigation, Zuordnungen, Resetfehler, Pop-up-Quittierung,
veraltete Meldungen und neue Eingänge während der Speicherung. Keine echte HA-,
Handy-, Pushover- oder Browser-Mod-Abnahme hier durchgeführt. Siehe VALIDATION.md.

## Technische Grenzen

Titel höchstens 80, Nachricht höchstens 1024 Zeichen nach Ersetzung. Platzhalter:
{regel}, {quelle}, {bereich}, {alarmtyp}, {status}. Für Textausgänge bleiben die
bisherigen Grenzen erhalten. Benachrichtigungen benötigen eingerichtete HA-App- oder
Pushover-Ziele. Pushover-Kontogeräte sind keine auswählbaren HA-Geräte: ihre exakten Namen
werden im optionalen Pushover-Feld angegeben. Aktionen heißen notify.pushover oder
notify.pushover_*; andere Namen werden nicht automatisch erkannt.

Browser-Pop-ups benötigen ein verbundenes, registriertes Browser-Mod-Dashboard, etwa in
Fully Kiosk. Kein automatisches Wecken, kein systemweites Android-Overlay und kein
automatisches Schließen bei Reset. Andere Pop-up-Automationen können die Anzeige ersetzen.
An HA übergeben ist keine Bestätigung von Empfang/Anzeige/Lesen auf dem Endgerät.

Ereignisse werden weiterhin als aktueller gewünschter Meldungsstand abgeglichen,
nicht als unbegrenzte Nachrichtenschlange. Unter schnell aufeinanderfolgenden Änderungen
können überholte Meldungen durch den neueren Zustand ersetzt werden. Erfolgreiche
Empfänger werden beim unveränderten Zustand nicht fortlaufend angeschrieben. Manuelles
Wiederholen eines unklaren Versandversuchs kann trotzdem doppelt zustellen.

## Primärquellen

- [Browser-Mod-Aktionen und Pop-up-Knöpfe](https://github.com/thomasloven/hass-browser_mod/blob/master/documentation/services.md)
- [HA-App-Benachrichtigungen](https://companion.home-assistant.io/docs/notifications/notifications-basic/)
- [Pushover in HA](https://www.home-assistant.io/integrations/pushover/)

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
