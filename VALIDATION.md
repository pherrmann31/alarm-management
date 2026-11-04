# Prüfbericht Alarm Management v1.1.0

04.11.2026. 239 Offline-Tests bestanden. Python-Syntax, JSON-Dateien, Übersetzungsschlüssel/-Platzhalter und Flow-Verweise geprüft. ZIP-Struktur und Dateiinhalt geprüft; SHA256 liegt bei.

Fünf neue Upgrade-Regressionen: v0.9-Optionen mit Benachrichtigungen unverändert übernehmen; aktive gespeicherte Alarme erhalten; fehlende Felder älterer Gruppenentwürfe ergänzen; beschädigte Werte ohne stille Löschung mit benannter Fehlerstufe ablehnen; ungültige Gruppenreferenzen benennen. Die bestehenden 234 Tests bleiben enthalten (u.a. gleichzeitige Ausgaben, Ereignisse, Gruppen, automatische Aufnahme und Eager-Task-Unload).

Getestet mit expliziten HA-Testdoubles, nicht an einem laufenden Home Assistant. Keine Prüfung physischer Melder, Sirenen, MQTT-Broker, Push-Zustellung oder Browser-Pop-ups. Kein hassfest-Lauf. Die konkrete Ursache auf dem Benutzer-HA ist ohne dessen Protokoll nicht abschließend bestätigt; im Screenshot wird alter Code 0.7.0 gemeldet.

Diese Version ist eine Fehlerbehebungs-/Testausgabe mit Versionsnummer 1.1.0. Der noch offene Komfortumfang der v1-Entwicklung ist in README dokumentiert.
