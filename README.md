# ChurchAdmin

![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2-green?logo=django&logoColor=white)
![LDAP](https://img.shields.io/badge/LDAP-OpenLDAP-orange?logo=openldap)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5.1-purple?logo=bootstrap&logoColor=white)
![License](https://img.shields.io/badge/License-AGPL--3.0-blue)
![Status](https://img.shields.io/badge/Status-Production-brightgreen)

Webbasiertes Gemeinde-Verwaltungssystem fuer Freikirchen mit LDAP-Backend, E-Mail-Verwaltung und DSGVO-Compliance.

## Features

### Benutzerverwaltung
- LDAP-basierte Authentifizierung (django-auth-ldap)
- Vollstaendiges CRUD fuer Benutzer mit Foto-Upload und Cropper
- Familienverwaltung mit Hierarchie (Oberhaupt/Ehepartner/Kind/Angehoeriger)
- Heirats-Workflow (LDAP move_user, Namensaenderung)
- Account-Deaktivierung mit Warn-E-Mails an Admins
- Self-Registration mit E-Mail-Verifizierung, CAPTCHA, Honeypot

### Berechtigungssystem
- Gruppen-basierte Berechtigungsmatrix (Admin-UI)
- Rollen: Pastor, Aeltester, Diakon, Sekretariat
- Feingranulare Rechte: view_members, edit_members, manage_mail, send_massmail, etc.

### Gemeindeliste & Export
- Familien-basierte Gemeindeliste mit Rollen-Icons
- PDF-Export (Landscape A4, DejaVuSans fuer Unicode)
- DSGVO-konform: Opt-out fuer Gemeindeliste-Sichtbarkeit

### Massen-E-Mail (Phase 13)
- TinyMCE WYSIWYG-Editor (selbst gehostet, kein API-Key)
- Empfaenger per Checkboxen: Mitglieder/Besucher/Angehoerige/Gaeste/Gruppen
- Personalisierung mit `[[vorname]]`, `[[nachname]]`, `[[name]]`
- Vorlagen-System (Du/Sie-Varianten) mit `manage.py seed_templates`
- Test-Mail, Versandprotokoll, Opt-out-Link in jeder Mail
- Editierbarer Footer mit DSGVO-Hinweisen

### DSGVO-Compliance (Phase 12)
- Datenschutzerklaerung und Impressum (editierbar im Admin)
- DSGVO-Auskunftsseite: Alle eigenen Daten einsehen und exportieren (JSON)
- Einwilligungsverwaltung: Opt-out-Verfahren mit Consent-Log
- Recht auf Vergessenwerden: Loeschantrag mit Admin-Benachrichtigung
- Familienoberhaupt verwaltet Consents fuer Kinder (ab 16 selbstverwaltet)
- Signierter Opt-out-Link in jeder E-Mail (ohne Login)

### Ticket-System (Phase 10)
- Bug-Reports, Feature-Requests, Aufgaben, Fragen
- Prioritaeten, Status-Workflow, Kommentare
- Zuweisung, Filter, Statistiken

### Backup & Recovery
- LDAP-Daten-Export (LDIF)
- Schema-Backup (slapcat -n0 + lokale LDIF-Dateien)
- Backup-Dashboard mit Download/Restore
- Bareos-Integration

## Tech Stack

| Komponente | Technologie |
|-----------|-------------|
| Backend | Django 4.2 / Python 3.13 |
| Authentifizierung | OpenLDAP / django-auth-ldap |
| Frontend | Bootstrap 5.1 / Bootstrap Icons |
| WYSIWYG | TinyMCE 6 (selbst gehostet) |
| Foto-Crop | Cropper.js |
| PDF | ReportLab mit DejaVuSans |
| CAPTCHA | django-simple-captcha |
| Deployment | Gunicorn + nginx + systemd |
| Backup | Bareos LDAP-Plugin |

## Installation

### Voraussetzungen

- Python 3.11+
- OpenLDAP (slapd)
- nginx
- Postfix (E-Mail-Versand)

### Setup

```bash
# Repository klonen
git clone https://github.com/Beerlesklopfer/ChruchAdmin.git
cd ChruchAdmin

# Virtual Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Datenbank initialisieren
python main/manage.py migrate

# Standard-Berechtigungen und Templates
python main/manage.py seed_templates

# Superuser erstellen
python main/manage.py createsuperuser

# Entwicklungsserver
python main/manage.py runserver
```

### Deployment (Produktion)

```bash
# Deploy-Script ausfuehren (rsync, migrate, collectstatic, restart)
sudo bash deploy.sh
```

Das Deploy-Script:
- Synchronisiert Dateien nach `/usr/share/python/ChruchAdmin/`
- Erstellt/aktualisiert venv und Abhaengigkeiten
- Fuehrt Migrationen und collectstatic aus
- Setzt Standard-Berechtigungen und AppSettings
- Aktualisiert Mail-Vorlagen (`seed_templates`)
- Installiert sudoers fuer Schema-Backup
- Startet den Gunicorn-Service neu

### LDAP-Schema

Eigene Schema-Erweiterungen muessen einmalig angewendet werden:

```bash
# familyRole Attribut (head/spouse/child/dependent)
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_familyRole.ldif
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_familyRole_step2.ldif

# accountDisabled Attribut (TRUE/FALSE)
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_accountDisabled.ldif
```

## Konfiguration

Alle Einstellungen sind im Django-Admin unter **Anwendungseinstellungen** editierbar:

| Setting | Beschreibung |
|---------|-------------|
| `church_name` | Name der Gemeinde |
| `church_address` | Anschrift |
| `church_email` | Kontakt-E-Mail |
| `church_contact_person` | Verantwortlicher |
| `church_domain` | Domain |
| `privacy_contact_person` | Datenschutz-Ansprechperson |

## Projektstruktur

```
ChruchAdmin/
├── main/              # Django-Projekt (settings, urls, wsgi)
│   ├── ldap_manager.py   # Zentrale LDAP-Verwaltungsklasse
│   └── forms.py          # Formulare
├── authapp/           # Authentifizierung, Views, Berechtigungen
│   ├── views.py          # Haupt-Views (~3000 Zeilen)
│   ├── export_views.py   # PDF/vCard Export
│   └── permissions_views.py
├── mailing/           # Massen-E-Mail-System
├── privacy/           # DSGVO-Compliance
├── tickets/           # Ticket & Bug Tracking
├── templates/         # Django-Templates
├── static/            # CSS, JS, TinyMCE, Cropper.js
├── ldap/              # LDAP-Schema-Erweiterungen
├── config/            # sudoers, Systemkonfiguration
└── deploy.sh          # Deployment-Script
```

## Screenshots

*Screenshots folgen*

## Lizenz

AGPL-3.0

## Autor

Joerg Bernau — [admin@example.de](mailto:admin@example.de)

Entwickelt mit Unterstuetzung von [Claude Code](https://claude.ai/claude-code) (Anthropic).
