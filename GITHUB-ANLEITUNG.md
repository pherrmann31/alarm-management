# GitHub und HACS — Ersteinrichtung

Vorbereitet für pherrmann31/alarm-management, Version 0.7.0.
Dieses Paket wurde lokal erstellt. Es wurde noch nichts auf GitHub veröffentlicht.

## 1. Repository auf GitHub anlegen

1. https://github.com/new öffnen und anmelden.
2. Owner: pherrmann31. Repository name: alarm-management.
3. Description: Konfigurierbare Alarmverwaltung für Home Assistant.
4. Public auswählen. HACS unterstützt dafür öffentliche GitHub-Repositories.
5. Add a README aktivieren. Dann Create repository anklicken.

## 2. Dateien hochladen

1. Das ZIP alarm-management-github-v0.7.0.zip am PC vollständig entpacken.
2. Im neuen Repository Add file → Upload files anklicken.
3. Den Ordner custom_components sowie tests und die Dateien README.md, hacs.json,
   VALIDATION.md und GITHUB-ANLEITUNG.md aus dem entpackten Paket in die Uploadfläche ziehen.
   Optional die .gitignore-Datei ebenfalls hochladen.
4. Den äußeren Entpackordner NICHT mitziehen und NICHT das ZIP als Datei hochladen.
5. Unten Commit changes anklicken und auf main speichern.
6. Auf der Startseite müssen custom_components, tests, hacs.json und README.md liegen.
   Prüfen: custom_components/alarm_management/manifest.json muss erreichbar sein.
7. Auf der Repository-Startseite bei About über das Zahnrad die Topics home-assistant,
   hacs und custom-integration eintragen.

Deine eigenen Logo-PNGs zusätzlich nach custom_components/alarm_management/brand/
hochladen, damit sie auch bei neuen Installationen dabei sind. Vorhandene eigene
Brand-Dateien werden durch persistent_directory bei HACS-Updates geschützt.
Keine HA-Konfiguration, .storage-Daten, Diagnoseexporte, Zugangsdaten oder Backups hochladen.
Das vorbereitete Paket enthält ausschließlich den Integrationscode, Dokumentation und Tests.

## 3. Erstes Release erstellen

1. Im Repository rechts Releases öffnen, dann Create a new release.
2. Bei Choose a tag den neuen Tag v0.7.0 anlegen; Zielbranch main.
3. Titel: Alarm Management v0.7.0.
4. Beschreibung z. B.: Erste HACS-Veröffentlichung; übersichtliche Konfiguration,
   echte Schalt- und Textausgaben. Hinweise und Prüfgrenzen in README und VALIDATION.
5. Als reguläres Release veröffentlichen: Publish release, kein Draft/Pre-release.
6. Kein zusätzliches ZIP hochladen. HACS nutzt hier die Dateien aus dem Repository
   am Release-Tag. zip_release ist absichtlich nicht aktiviert.

Wichtig: Erst alle Dateien vollständig hochladen, dann das Release anlegen.
Ein nachträglicher Commit verändert den Inhalt eines bestehenden Release-Tags nicht.

## 4. Vorhandene Installation in HACS übernehmen

1. Vollständiges HA-Backup erstellen. Testeingänge ausschalten und Testalarme zurücksetzen.
2. Vorhandene Alarm-Management-Integration in Geräte & Dienste behalten, nicht löschen.
3. HACS öffnen → oben rechts ⋮ → Benutzerdefinierte Repositories / Custom repositories.
4. URL https://github.com/pherrmann31/alarm-management eintragen.
5. Typ Integration wählen und hinzufügen.
6. In HACS nach Alarm Management suchen, öffnen, Version v0.7.0 herunterladen.
   Falls diese schon als installiert geführt wird, die Funktion Erneut herunterladen nutzen.
7. Home Assistant vollständig neu starten. Vorhandene Einstellungen und Entitäts-IDs
   bleiben erhalten; die Integration wird nicht ein zweites Mal hinzugefügt.
8. Version und Konfiguration prüfen, anschließend mit deinen Testhelfern abnehmen.

## 5. Künftige Updates

1. Geänderte Dateien hochladen und speichern.
2. Version in custom_components/alarm_management/manifest.json UND const.py erhöhen,
   z. B. auf 0.7.1. Syntax und Tests vor Veröffentlichung prüfen.
3. Ein neues reguläres Release mit passendem Tag v0.7.1 veröffentlichen.
4. HACS erkennt die neue Version bei der nächsten Prüfung; bei Bedarf im Repositorymenü
   Informationen aktualisieren. Die Aktualisierung erscheint in HA über die HACS-Updateentität,
   sofern diese aktiviert ist. Nicht zwingend sofort nach Veröffentlichung.
5. Update bewusst installieren und danach HA neu starten. Es gibt keine hier eingerichtete
   automatische Installation. Aktive Anforderungen können beim Neustart weiter ausgeführt werden.

Die öffentliche Aufnahme in den allgemeinen HACS-Katalog ist ein eigener späterer Schritt.
Für dein benutzerdefiniertes Repository ist diese Aufnahme nicht erforderlich.
Es wird hier keine Veröffentlichungslizenz vorgegeben; die Lizenzwahl ist noch offen.

## Quellen

- GitHub: https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- HACS-Struktur: https://hacs.dev/docs/publish/integration/
- HACS-Manifest und Versionen: https://hacs.dev/docs/publish/start/
- HACS-Repository hinzufügen: https://hacs.dev/docs/faq/custom_repositories/
