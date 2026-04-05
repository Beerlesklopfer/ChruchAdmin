# CLAUDE.md - Projektanweisungen fuer Claude Code

## Projekt

ChurchAdmin — Webbasiertes Gemeinde-Verwaltungssystem fuer die eine Freikirche
Django 4.2, OpenLDAP, Bootstrap 5, Python 3.13.

## Architektur

- **main/** — Django-Projekt (settings, urls, wsgi, ldap_manager.py, forms.py)
- **authapp/** — Hauptapp: Views (~3000 Zeilen), Models, Export, Permissions, Password-Reset
- **mailing/** — Massen-E-Mail mit TinyMCE, Vorlagen, Opt-out
- **privacy/** — DSGVO: Datenschutz, Impressum, Consent, Loeschantraege
- **tickets/** — Ticket & Bug Tracking
- **templates/** — Django-Templates (nicht in den Apps!)
- **static/** — CSS, JS, TinyMCE, Cropper.js (vendor/)
- **ldap/** — LDAP-Schema-Erweiterungen (LDIF)

## Wichtige Konventionen

- **Commit nur nach Aufforderung** — Nicht automatisch committen
- **Jede Aenderung wird sofort deployed** — `sudo bash deploy.sh`, nicht nachfragen
- **Organisations-E-Mail und Rolle/Position** sind NUR vom Admin aenderbar, nie vom Benutzer
- **Gemeindename** aus `AppSettings.get('church_name')`, nie hardcoden
- **Templates** liegen unter `/templates/`, nicht in den App-Verzeichnissen
- **Statische Dateien** von Drittanbietern unter `static/vendor/`
- **Keine CDN-API-Keys** — Bibliotheken lokal hosten (TinyMCE, Cropper.js)

## LDAP

- Server: `ldaps://ldap.example-church.de`
- Base DN: `dc=example-church,dc=de`
- Users: `ou=Users,dc=example-church,dc=de`
- Groups: `ou=Groups,dc=example-church,dc=de`
- Nested Users: Kinder unter `cn=Kind,cn=Elternteil,ou=Users,...`
- Custom Attribute: `familyRole` (head/spouse/child/dependent)
- Custom Attribute: `accountDisabled` (TRUE/FALSE)
- `LDAPManager` ist die zentrale Klasse in `main/ldap_manager.py`
- Binaere Attribute (jpegPhoto) NICHT mit decode_attribute() dekodieren

## Berechtigungen

- `PermissionMapping` Model mit `PERMISSION_CHOICES` — dort neue Rechte eintragen
- Berechtigungsmatrix liest dynamisch aus dem Model, keine hardcoded Listen
- Context Processor `church_settings` und `user_permissions` in `authapp/context_processors.py`
- `get_or_create_django_user(cn)` erstellt Django-User aus LDAP wenn noetig

## Management Commands

- `python manage.py seed_templates` — Mail-Vorlagen erstellen/aktualisieren
- `python manage.py backup_ldap --type=full` — LDAP-Backup inkl. Schema

## Deploy

```bash
sudo bash deploy.sh
```

Deploy-Ziel: `/usr/share/python/ChruchAdmin/`
Service: `churchadmin.service` (Gunicorn + systemd socket)

## Tests

```bash
python main/manage.py check
python main/manage.py test
```
