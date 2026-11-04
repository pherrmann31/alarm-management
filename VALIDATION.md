# Prüfung v1.0.0b1

Datum: 04.11.2026. 234 automatisierte Offline-Tests bestanden.

Geprüft: Python-Syntax, JSON, Übersetzungsschlüssel und Platzhalter, native Flow-Ziele einschließlich Gruppen-Mixin; bestehende Alarm-/Ausgabetests; Gruppenaggregation mit einzelnen Melderdetails; gespeicherte Gruppenalarme; unbekannte und leere Gruppen; idempotente Aufnahme; manuelle Verschiebung; nächste Aufnahme in Standard; Ausschluss von Batterie-Entitäten; Tasterkriterien; Ereignispuls ohne Wiederholung alter Ereignisse; automatischer Regelaufbau; Ausgabegruppenauflösung; Löschschutz; automatische Aufnahme eines bereits aktiven Melders im laufenden Manager; bestehende Eager-Task-/Unload-Regressionen.

HA-Adapter verwenden ausdrücklich Testdoubles. Kein Live-HA-, MQTT-Broker-, X-Sense-, Zigbee-, Handy-, Pushover-, Browser-Mod- oder Sirenentest. Kein hassfest-Lauf. Der beiliegende Testbericht enthält die einzelnen Testnamen.

Status: erster v1.0-Testrelease. Die README nennt enthaltene Funktionen und noch offene Punkte des besprochenen Gesamtumfangs. Keine Freigabe als endgültige v1.0.
