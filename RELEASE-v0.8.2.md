# Alarm Management v0.8.2 — Hänger beim Speichern behoben

Behebt einen reproduzierten Fehler beim Neuladen der Integration: sofort abgeschlossene
Hintergrundaufgaben blieben in der Aufgabenliste, drain geriet in eine Warteschleife ohne
echte Unterbrechung und konnte dadurch die HA-Ereignisschleife blockieren.

Erledigte Aufgaben werden jetzt zuverlässig bereinigt. Vier neue Prüfungen mit realer
eager_task_factory und externem Zeitwächter bestehen; insgesamt 201 Offline-Tests.
Die Formular-Korrektur aus v0.8.1 ist enthalten. Kein Live-HA-Test hier durchgeführt.

Bei betroffenem System zuerst Neustart zur Wiederherstellung. Dann Backup erstellen,
diese Version herunterladen und HA neu starten. Erst nach Anzeige von 0.8.2 erneut
speichern. Bestehende Konfiguration behalten. Keine zusätzliche Datenmigration.
Weiterhin als Testversion veröffentlichen und mit Testhelfern abnehmen.
