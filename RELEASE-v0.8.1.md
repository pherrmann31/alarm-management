# Alarm Management v0.8.1 — Formularfehler behoben

Behebt „Nicht alle Pflichtfelder sind ausgefüllt“ beim Speichern einer Push-Nachricht
trotz korrekt ausgewähltem Handy. HA kann jetzt die Werte innerhalb aller Abschnitte
vorbelegen; insbesondere ist Pushover-Priorität Normal vorhanden, ohne den optionalen
Abschnitt öffnen zu müssen. Auch bestehende Regel-, Text- und Formatwerte bleiben
beim Öffnen ihrer Abschnitte vorbelegt.

197 Offline-Tests bestanden, darunter vier neue Prüfungen der HA-Frontend-Initialisierung.
Syntax und Paketstruktur geprüft. Kein Live-HA-/Gerätetest hier durchgeführt.

Nach Installation HA neu starten, den alten Konfigurationsdialog schließen und erneut
öffnen. Vor Update Backup erstellen. Keine Datenmigration oder Versandlogikänderung
gegenüber v0.8.0. Weiterhin als Testversion veröffentlichen.
