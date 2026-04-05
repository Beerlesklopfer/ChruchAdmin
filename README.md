# ChurchAdmin

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-green?logo=django&logoColor=white)
![LDAP](https://img.shields.io/badge/LDAP-OpenLDAP-orange?logo=openldap)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.1-purple?logo=bootstrap&logoColor=white)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Status](https://img.shields.io/badge/Status-Production-brightgreen)

## Was ist ChurchAdmin?

ChurchAdmin ist eine Webanwendung fuer Gemeinden, die ihre Mitglieder, Familien, Gruppen und Kommunikation an einem Ort verwalten moechten — einfach, sicher und datenschutzkonform.

**Fuer wen ist es gedacht?**
- Pastoren und Gemeindeleitung, die den Ueberblick behalten wollen
- Sekretariat und Mitarbeiter, die Mitgliederdaten pflegen
- Gemeindemitglieder, die ihre eigenen Daten verwalten moechten

## Was kann es?

### Mitglieder & Familien
- Mitglieder mit Kontaktdaten, Foto und Gruppenzugehoerigkeit verwalten
- Familien als Einheit sehen: Oberhaupt, Ehepartner, Kinder
- Neue Mitglieder koennen sich selbst registrieren (mit Genehmigung durch die Leitung)
- Jedes Mitglied hat ein eigenes Profil und kann seine Daten selbst pflegen

### Gemeindeliste
- Uebersichtliche Liste aller Familien und Mitglieder
- Als PDF exportierbar — praktisch fuer Hauskreise oder Gebetslisten
- Jedes Mitglied entscheidet selbst, ob es in der Liste erscheint (Datenschutz)

### Rundschreiben & E-Mail
- Gemeindebriefe und Ankuendigungen direkt aus der Anwendung versenden
- Vorlagen in Du- und Sie-Form, personalisiert mit Namen
- Empfaenger nach Gruppen, Status oder manuell waehlbar
- Jede E-Mail enthaelt einen Abmelde-Link (DSGVO-konform)

### Berechtigungen
- Wer darf was? Uebersichtliche Matrix fuer alle Gruppen
- Rollen wie Pastor, Aeltester, Diakon, Sekretariat
- Feingranular: Wer darf Mitglieder sehen, bearbeiten, E-Mails versenden?

### Datenschutz (DSGVO)
- Impressum und Datenschutzerklaerung — editierbar, ohne Programmierkenntnisse
- Jedes Mitglied kann seine gespeicherten Daten einsehen und exportieren
- Einwilligungen verwalten: E-Mail-Empfang, Sichtbarkeit in der Gemeindeliste
- Familienoberhaupter verwalten den Datenschutz fuer ihre Kinder
- Ab 16 Jahren koennen Jugendliche ihre Einstellungen selbst verwalten
- Recht auf Vergessenwerden: Loeschantrag mit einem Klick

### Tickets & Fehlerberichte
- Probleme melden, Wuensche aeussern, Aufgaben verteilen
- Jedes Gemeindemitglied kann Tickets erstellen
- Uebersichtlich mit Status, Prioritaet und Kommentaren

### Sicherheit
- Passwort-Zuruecksetzung per E-Mail (an die private Adresse)
- Deaktivierte Accounts werden beim Login blockiert
- Bei verdaechtigen Login-Versuchen wird die Leitung benachrichtigt
- Automatische Datensicherung (LDAP-Backup mit Schema)

## Fuer Gemeindemitglieder

Nach der Anmeldung unter `wir.example-church.de` koennen Sie:

1. **Ihr Profil bearbeiten** — Telefon, Adresse, Foto, Passwort
2. **Ihre Familie sehen** — Familienoberhaupter koennen Daten der Kinder pflegen
3. **Die Gemeindeliste einsehen** — und als PDF herunterladen
4. **Datenschutz verwalten** — unter "Meine Daten (DSGVO)" im Menue
5. **Probleme melden** — unter "Tools → Tickets & Bugs"

---

## Fuer Administratoren

### Voraussetzungen

- Linux-Server mit Python 3.11+
- OpenLDAP (slapd) als Benutzerverwaltung
- nginx als Webserver
- Postfix fuer E-Mail-Versand

### Installation

```bash
git clone https://github.com/Beerlesklopfer/ChruchAdmin.git
cd ChruchAdmin

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python main/manage.py migrate
python main/manage.py seed_templates
python main/manage.py createsuperuser
python main/manage.py runserver
```

### Produktiv-Deployment

```bash
sudo bash deploy.sh
```

Das Script kuemmert sich um alles: Dateien synchronisieren, Datenbank aktualisieren, E-Mail-Vorlagen einrichten, Dienst neu starten.

### LDAP-Schema einmalig erweitern

```bash
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_familyRole.ldif
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_familyRole_step2.ldif
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_accountDisabled.ldif
```

### Einstellungen

Alle Einstellungen sind im Admin-Bereich unter **Anwendungseinstellungen** aenderbar — kein Programmieren noetig:

| Einstellung | Beschreibung |
|-------------|-------------|
| Gemeindename | Wird ueberall angezeigt (Titel, Footer, E-Mails) |
| Anschrift | Fuer Impressum und Datenschutzerklaerung |
| Kontakt-E-Mail | Antwort-Adresse fuer Gemeinde-Mails |
| Ansprechperson | Verantwortlicher im Sinne der DSGVO |

### Tech Stack

| Was | Womit |
|-----|-------|
| Anwendung | Django 4.2 / Python 3.13 |
| Benutzerverwaltung | OpenLDAP |
| Oberflaeche | Bootstrap 5 |
| E-Mail-Editor | TinyMCE 6 |
| PDF-Export | ReportLab |
| Deployment | Gunicorn + nginx + systemd |
| Backup | Bareos LDAP-Plugin |

### Projektstruktur

```
ChruchAdmin/
├── main/          — Projekt-Konfiguration und LDAP-Anbindung
├── authapp/       — Benutzerverwaltung, Login, Berechtigungen
├── mailing/       — Rundschreiben und E-Mail-Vorlagen
├── privacy/       — Datenschutz, Impressum, Einwilligungen
├── tickets/       — Ticket-System und Fehlerberichte
├── templates/     — Alle HTML-Vorlagen
├── static/        — Design, Schriften, Editoren
├── ldap/          — LDAP-Schema-Erweiterungen (LDIF)
├── docs/          — Dokumentation (Architektur, Postfix, Nextcloud, Schemas)
├── tests/         — Tests und Fehlerbehebung
└── deploy.sh      — Installations-Script
```

## Dokumentation

| Dokument | Beschreibung |
|----------|-------------|
| [Architektur](docs/architecture.md) | Gesamtuebersicht: ChurchAdmin + LDAP + Postfix + Nextcloud |
| [Postfix](docs/postfix.md) | E-Mail-Konfiguration mit LDAP-Anbindung |
| [Nextcloud](docs/nextcloud.md) | Nextcloud LDAP-Integration |
| [Konfiguration](docs/configuration.md) | .env, AppSettings, LDAP — alles fuer eine neue Gemeinde |
| [LDAP-Schemas](docs/ldap-schemas.md) | Alle Schemas mit Installationsanleitung |
| [Troubleshooting](tests/TROUBLESHOOTING.md) | Fehlerbehebung und nuetzliche Befehle |

## Screenshots

*Screenshots folgen*

## Lizenz

AGPL-3.0 — Der Quellcode ist frei verfuegbar. Wenn Sie ChurchAdmin weiterentwickeln und oeffentlich betreiben, muessen die Aenderungen ebenfalls veroeffentlicht werden.

## Autor

Der Autor — [admin@example.de](mailto:admin@example.de)

Entwickelt mit Unterstuetzung von [Claude Code](https://claude.ai/claude-code) (Anthropic).
