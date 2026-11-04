# Prüfbericht v1.2.0

04.11.2026. 247 automatisierte Offline-Tests bestanden. Python-Syntax, JSON, Versionskonsistenz, Übersetzungsschlüssel und Platzhalter, Flow-Ziele und ZIP-Inhalt geprüft.

Neue Regressionen: vollständiger Assistent mit Eingängen, Ausgängen, vorausgewählten Regelbedingungen und späteren Nachrichten; genau ein Speichern und Neuladen; Rückkehr zur Übersicht; Entwurf verwerfen ohne Schreiben; Konfliktschutz bei zwischenzeitlichen Änderungen; Bestätigung vor Übernahme; Zurücknavigation ohne Verlust; gespeicherte Konfiguration bei Reload-Fehler erhalten; bewusst leere Nachrichten-Zuordnung beim Zurückwechseln erhalten; vorhandene Definitionen beim Abbrechen erhalten.

Die 239 bisherigen Tests bleiben enthalten. Tests verwenden explizite HA-Doubles. Kein Test im laufenden HA, kein Browser-Renderingtest, kein hassfest-Lauf und kein Versand an reale Geräte. Vor Live-Abnahme vollständiges Backup erstellen.
