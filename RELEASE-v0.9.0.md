# Alarm Management v0.9.0

Eigene Benachrichtigungsverwaltung neben Eingangsquellen, Regeln und Schalt-/Textausgängen.
Die Typen heißen Benachrichtigung und Pop-up Nachricht Browser; kein überflüssiges
Zielentitätsfeld bei ihrer Anlage. Regeln wählen beide Gruppen getrennt aus; vorhandene
IDs und Zuordnungen bleiben erhalten. Regelauswahl ohne UND/ODER-Zusätze.

Abgelehnter Reset meldet Regel und Grund an die zugeordneten Empfänger. Browser-Pop-ups
erhalten einen Quittieren-Knopf: nur angezeigte Alarmvorkommen werden nach Serverprüfung
quittiert, Ergebnis wird gespeichert und zurückgemeldet. Alte Meldungen quittieren keine
neuen Auslösungen oder neu hinzugekommenen Quellen. Schließen bleibt eine reine Anzeigeaktion.

Neue Einträge haben Quittierungs-/Resettexte vorausgefüllt. Bestehende Texte und leere
Werte bleiben erhalten. Bei leerem Quittierungstext erfolgt dennoch eine Bestätigung
nach Pop-up-Quittierung; Resetfehler werden ebenfalls gemeldet.

218 Offline-Tests bestanden; kein Live-HA-/Endgerätetest. Die Hänger- und Formularkorrekturen
aus v0.8.1/v0.8.2 sind enthalten. Kein neues Speicherformat, aber neue Protokollereignisse:
Downgrade nur mit vollständigem vorherigem Backup. Vor Update Backup, danach HA-Neustart
und Abnahme mit Testhelfern. Zunächst als Pre-release veröffentlichen.
