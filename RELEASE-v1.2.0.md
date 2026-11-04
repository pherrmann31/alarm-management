# Alarm Management v1.2.0 – Einrichtungsassistent

Die Konfigurationsübersicht zeigt jetzt Status & Überblick, Assistenten & Gruppen, Eingangsquellen, Ausgänge verwalten, Regelverwaltung und Benachrichtigungen.

Der neue Assistent führt durch Eingänge → Ausgänge → Regeln → Benachrichtigungen. Neue Eingänge und Ausgänge werden in neuen Regeln vorgeschlagen. Später angelegte Benachrichtigungen können den Regeln vor dem Abschluss zugeordnet werden. Entwurf mit Weiter/Zurück, abschließende Übersicht, einmaliges Speichern/Neuladen und Rückkehr zur Konfigurationsübersicht. Abbruch speichert nichts; konkurrierende Konfigurationsänderungen werden nicht überschrieben.

247 Offline-Tests bestanden. Live-HA-Abnahme steht aus. Bestehende Konfiguration bleibt erhalten. Vor dem Update Backup erstellen, v1.2.0 in HACS installieren und HA vollständig neu starten.

Release-Tag v1.2.0 neu auf dem Commit mit Manifest-Version 1.2.0 erstellen. Vorhandene Tags nicht verschieben.
