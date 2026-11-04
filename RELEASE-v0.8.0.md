# Alarm Management v0.8.0

Push-Nachrichten und Tablet-Overlays sind neue, Regeln zuordenbare Ausgangstypen.
HA-App-Ziele und Browser-Mod-Geräte lassen sich mehrfach auswählen. Titel, Alarmtext
und optionale Quittierungs-/Ruhetexte sind einstellbar. Pushover über bestehende
notify.pushover*-Aktionen mit optionalen Gerätenamen und Priorität -2 bis 1.

Versandnachweise werden je Empfänger gespeichert. Keine automatische Wiederholung
unklarer Push-Aufrufe; erfolgreiche Ziele bleiben bei manueller Wiederholung ausgelassen.
„An HA übergeben“ bestätigt keine Anzeige auf dem Endgerät. Browser Mod benötigt ein
verbundenes Dashboard; kein automatisches Aufwecken oder Schließen beim Reset.

Vor Update Backup erstellen. Ausgangsoptionen werden auf Version 2 ergänzt, Store bleibt 5.
Bestehende Konfiguration behalten, nach Installation HA neu starten und neue Ausgänge
mit Testhelfern abnehmen. Downgrade über vollständiges vorheriges Backup.

193 Offline-Tests sowie Syntax-/Strukturprüfung bestanden; kein Live-Gerätetest.
Siehe README und VALIDATION für Umfang, Einrichtung und Grenzen.
