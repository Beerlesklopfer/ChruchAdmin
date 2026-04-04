# Church Admin - TODO Liste

## Nächste Schritte (Empfohlene Priorität)

### Sofort (Hohe Priorität)
1. **Family Tree Visualisierung** - Interaktiver Baum für Familien-Hierarchie
2. **Gruppen-Detail-Ansicht** - Vollständige CRUD-Operationen für Gruppen
3. **Mail-Verwaltung (Phase 6)** - Mail-Domains, Routing, Alias-Verwaltung
4. **Bulk-Operationen** - Mehrere Benutzer gleichzeitig bearbeiten

### Kurzfristig (Diese Woche)
1. **Testing** - Unit Tests für LDAPManager und Views
2. **Documentation** - README.md erweitern mit Setup-Anleitung
3. **Performance** - LDAP-Query-Caching implementieren
4. **Security** - Rate Limiting für Login-Versuche

### Mittelfristig (Diesen Monat)
1. **Self-Registration (Phase 9)** - Öffentliches Formular mit Pastor-Genehmigung
2. **DSGVO-Compliance (Phase 12)** - Datenschutzerklärung, Einwilligungen
3. **Backup & Recovery** - LDAP-Backup und Restore-Funktionen
4. **Production Deployment** - Docker-Container, HTTPS, Monitoring

## Kürzlich erledigte Aufgaben (2026-04-04)

### Benutzer-Dashboard & Familienverwaltung ✅
- [x] **Benutzer-Dashboard**: Persoenliches Dashboard fuer alle Benutzer (`/dashboard/`)
- [x] **Familienverwaltung**: Vaeter koennen ihre Familienmitglieder verwalten
- [x] **Familienansicht**: Kinder/Angehoerige koennen Familiendaten einsehen (read-only)
- [x] **Login-Redirect**: Admins → Admin-Dashboard, normale User → Benutzer-Dashboard
- [x] **Navigation**: "Mein Bereich" fuer alle eingeloggten User

### CAPTCHA & Passwort-Reset ✅
- [x] **CAPTCHA**: django-simple-captcha fuer Passwort-Reset-Formulare
- [x] **Passwort-Reset an private Mail**: Reset-Mail geht an mailRoutingAddress (nicht Org-Mail)
- [x] **Suche per privater Mail**: Passwort-Reset funktioniert mit Username, Org-Mail oder privater Mail
- [x] **LDAP change_password Fix**: Bytes-Encoding fuer SSHA-Passwort-Hash korrigiert

### Mail-Verwaltung ✅
- [x] **Mail-Attribute im Admin**: Alle LDAP-Mail-Attribute (mail, mailRoutingAddress, mailAliasAddress, mailQuota, mailAliasEnabled, mailRoutingEnabled) editierbar
- [x] **CRUD-Listen**: Dynamische Add/Remove-Listen fuer Multi-Value-Mail-Attribute
- [x] **Mail-Sub-Template**: Wiederverwendbares Template fuer E-Mail-Listen
- [x] **AppSettings im Django-Admin**: E-Mail-Versand-Einstellungen (SMTP, Absender, Reply-To) konfigurierbar
- [x] **Benachrichtigungs-E-Mail**: Benutzer koennen eigene Benachrichtigungsadresse auf Profilseite setzen

### Profil & Benutzerdaten ✅
- [x] **Editierbares Profil**: Benutzer koennen eigene Daten aendern (Name, Telefon, Mobil, Anschrift, Geburtstag)
- [x] **Geburtstag-Widget**: HTML5 date-Input mit LDAP generalizedTime-Konvertierung
- [x] **Organisations-Email read-only**: Mail-Adresse und Rolle/Position nur durch Admin aenderbar

### Deployment ✅
- [x] **Deploy-Script**: `deploy.sh` mit rsync, venv, migrate, collectstatic, Service-Restart
- [x] **DB-Schutz**: Produktions-DB (db.sqlite3) wird beim Deploy nicht mehr ueberschrieben
- [x] **LOGIN_URL**: Korrekte Weiterleitung auf `/login/` statt Django-Default `/accounts/login/`
- [x] **Static Files Fix**: Duplikat-Admin-Statics entfernt

## Erledigte Aufgaben (2026-02-01)

### Login & Authentifizierung ✅
- [x] **Email-Login-Unterstützung**: Benutzer können sich nun mit E-Mail-Adresse statt Username anmelden
- [x] **Email-zu-Username-Normalisierung**: Automatische LDAP-Lookup für cn basierend auf E-Mail
- [x] **IntegrityError-Handling**: Robuste Fehlerbehandlung bei Login mit bestehenden Usern
- [x] **Unique Email Constraint**: E-Mail-Adressen sind jetzt einzigartig in der Datenbank

### Email-System ✅
- [x] **EmailTemplate Model**: Editierbare E-Mail-Vorlagen im Admin-Bereich
- [x] **Willkommens-Email**: Automatische E-Mail bei Aufnahme in "Mitglieder"-Gruppe
- [x] **Template-Platzhalter**: Unterstützung für {{name}}, {{email}}, {{username}}, etc.

### UI/UX Verbesserungen ✅
- [x] **Toast-Notifications**: Verbesserte Sichtbarkeit des Close-Buttons mit Church CI
- [x] **Status-basierte Filterung**: Filter für Mitglieder, Besucher, Gäste, Ehepartner, Angehörige
- [x] **Live-Suche**: Debounced Live-Suche in Benutzer- und Mitgliederverwaltung
- [x] Autoconfig für gemeindedienste (iOS)

### Git & Deployment ✅
- [x] **Initial Git Commit**: Gesamtes Projekt ist jetzt versioniert
- [x] **.gitignore**: Korrekte Ignorierung von __pycache__, db.sqlite3, .venv, etc.

## Bugs

### Hohe Priorität
- [x] **Email-Login IntegrityError**: ✅ BEHOBEN - Login mit E-Mail funktioniert nun korrekt
- [ ] **First login after setup**: LDAP-Verbindung automatisch beim ersten Login nach Setup erstellen
- [x] **Captcha for password reset**: ✅ BEHOBEN - django-simple-captcha implementiert
- [x] **Gunicorn script fuer systemd**: ✅ BEHOBEN - Service laeuft, deploy.sh erstellt

### Mittlere Priorität
- [x] **LDAP Connection Error bei Login**: ✅ BEHOBEN - Besseres Exception-Handling implementiert
- [x] Passwort-Zuruecksetzen fuer LDAP-Benutzer ✅ BEHOBEN - Bytes-Encoding Fix
- [ ] Foto-Upload Validierung: Dateigröße und Format besser prüfen

### Niedrige Priorität
- [ ] Performance-Optimierung: LDAP-Abfragen cachen
- [ ] Responsive Design für mobile Geräte optimieren
- [ ] Tastaturkürzel für häufige Aktionen hinzufügen

## Features

### Phase 1: LDAP Connection Manager ✅
- [x] Zentrale LDAPManager-Klasse implementiert
- [x] Connection Pooling
- [x] Error Handling
- [x] Logging aller Operationen

### Phase 2: Corporate Identity ✅
- [x] Custom CSS mit Farbschema (Navy, Gold, Beige)
- [x] Navbar angepasst
- [x] Buttons mit Gold-Akzent
- [x] Cards mit Beige Background
- [x] Konsistentes Font-Styling

### Phase 3: Dashboard ✅
- [x] Statistiken (Benutzer, Gruppen, Mail-Domains)
- [x] Visualisierungen (Gruppen-Hierarchie, Familien-Übersicht)
- [x] Schnellzugriff-Links
- [x] Größte Familien klickbar als Filter
- [x] Mail-Domains klickbar
- [x] **Statistik-Karten klickbar** (Benutzer Gesamt → Benutzersuche, Gruppen Gesamt → Gruppenliste)

### Phase 4: Benutzerverwaltung ✅
- [x] Benutzer-Liste mit Suche und Filter
- [x] Benutzer-Detail-Ansicht
- [x] Benutzer erstellen (mit Auto-Open Dialog)
- [x] Benutzer bearbeiten
- [x] Benutzer löschen
- [x] Foto-Upload
- [x] Parent-Auswahl (Verwandtschaftsbeziehung änderbar)
- [x] **Suche nach Verwandtschaftsbeziehung, Elternnamen und Rolle** ✨
- [ ] Family Tree Visualisierung (interaktiver Baum)
- [ ] Bulk-Operationen (mehrere Benutzer gleichzeitig bearbeiten)

### Phase 5: Gruppenverwaltung ✅ (Teilweise)
- [x] Gruppen-Liste mit hierarchischer Einrückung
- [ ] Gruppen-Detail-Ansicht mit Mitgliedern
- [ ] Gruppe erstellen (mit Parent-Gruppe)
- [ ] Gruppe bearbeiten
- [ ] Gruppe löschen
- [ ] Mitglieder hinzufügen/entfernen
- [ ] Gruppen-Baum Visualisierung
- [ ] Drag-and-Drop zum Reorganisieren

### Phase 6: Mail-Verwaltung (TODO)
- [ ] Mail-Übersicht (alle konfigurierten Benutzer/Gruppen)
- [ ] Mail-Domains auflisten
- [ ] Mail-Domain erstellen
- [ ] Mail-Domain löschen
- [ ] Benutzer-Mail-Routing konfigurieren
- [ ] Gruppen-Mail-Adressen konfigurieren
- [ ] Alias-Verwaltung
- [ ] Bulk-Mail-Konfiguration
- [ ] Import/Export Mail-Konfigurationen

### Phase 7: Navigation & URL-Struktur ✅
- [x] URL-Pattern für alle LDAP-Funktionen
- [x] Navigation in base.html mit Dropdown
- [x] Breadcrumbs auf allen Seiten

### Phase 8: Error Handling & Logging ✅ (Erweitert)
- [x] Custom Exceptions definiert
- [x] Logging in LDAPManager
- [x] Django Messages für User Feedback
- [x] **LDAP Connection Error Handling** (verbessert mit LDAPConnectionError Exception)
- [x] **IntegrityError Handling** (bei Email-Login mit Fallback-Authentifizierung)
- [ ] Admin-Benachrichtigungen bei kritischen Fehlern
- [ ] Detaillierte Error-Pages

### Phase 8a: Email-Template-System ✅ (NEU)
- [x] EmailTemplate Model erstellt
- [x] Admin-Interface für Email-Templates
- [x] Template-Rendering mit Platzhaltern ({{name}}, {{email}}, etc.)
- [x] Automatische Willkommens-Email bei Mitglieder-Aufnahme
- [x] E-Mail-Konfiguration in settings.py
- [ ] Weitere Template-Typen (Passwort-Reset, Konto-Erstellt, etc.)

### Phase 9: Self-Registration (TODO)
- [ ] Öffentliches Registrierungsformular
- [ ] reCAPTCHA Integration (Bot-Schutz)
- [ ] RegistrationRequest Model
- [ ] Pastor-Genehmigungssystem
- [ ] E-Mail-Benachrichtigungen (an Pastor, an Benutzer)
- [ ] Automatische LDAP-Benutzer-Erstellung bei Genehmigung
- [ ] Rate Limiting (max 3 Registrierungen pro IP/Stunde)
- [ ] Honeypot Field gegen Bots
- [ ] Familie-Registrierung durch Väter

### Phase 10: Todo & Bug Tracking (TODO)
- [ ] Todo Model
- [ ] Bug Model
- [ ] Todo-Liste View
- [ ] Bug-Liste View
- [ ] Todo erstellen/bearbeiten/löschen
- [ ] Bug melden/bearbeiten/schließen
- [ ] Dashboard-Integration (Top 5 Todos, kritische Bugs)

### Phase 11: Verschlüsselte Notizen für Pastor/Älteste (TODO)
- [ ] **PersonNote Model** (mit Verschlüsselung)
- [ ] **Verschlüsselungs-Mechanismus** (AES-256 mit Fernet)
- [ ] **Notiz erstellen/bearbeiten** (nur für Pastor/Älteste)
- [ ] **Notizen-Übersicht** (pro Person)
- [ ] **Notizen-Verlauf** (Historie aller Änderungen)
- [ ] **Zugriffskontrolle** (nur Pastor/Älteste können Notizen sehen)
- [ ] **Verschlüsselungsschlüssel-Verwaltung** (pro Benutzer)
- [ ] **Audit-Log** (wer hat wann welche Notiz gelesen/bearbeitet)

### Phase 12: DSGVO-Compliance (TODO)
- [ ] **DSGVO-Hinweis Model** (individualisierbar)
- [ ] **DSGVO-Einwilligung** (Checkbox beim Registrieren)
- [ ] **DSGVO-PDF-Generator** (individualisierter Download)
- [ ] **Datenschutzerklärung** (anzeigen und akzeptieren)
- [ ] **Recht auf Vergessenwerden** (Benutzer löschen mit allen Daten)
- [ ] **Datenexport** (alle Daten als JSON/PDF)
- [ ] **Einwilligungsverwaltung** (Übersicht aller Einwilligungen)
- [ ] **Audit-Trail** (alle Zugriffe auf personenbezogene Daten)

## Verbesserungen

### UX/UI
- [x] **Modal/Dialog-Standard**: Alle Dialoge haben Titelleiste mit Close-Button (✅ implementiert)
- [ ] Keyboard Shortcuts (z.B. Strg+K für Schnellsuche)
- [ ] Dark Mode Toggle
- [ ] Erweiterte Filtermöglichkeiten (Datum, Rolle, etc.)
- [ ] Export-Funktionen (CSV, Excel) für Benutzer/Gruppen
- [ ] Druckansichten optimieren
- [ ] Inline-Editing (Edit-on-Click)

### Performance
- [ ] LDAP-Query-Caching implementieren
- [ ] Lazy Loading für große Listen
- [ ] Pagination für Benutzer/Gruppen-Listen verbessern
- [ ] Database Indexing für LDAPUserLog

### Sicherheit
- [ ] Two-Factor Authentication (2FA)
- [ ] Audit-Log für alle Admin-Aktionen
- [ ] CSRF-Token Validierung verstärken
- [ ] Input Sanitization verbessern
- [ ] Rate Limiting für Login-Versuche
- [ ] Session-Timeout konfigurierbar machen

### Dokumentation
- [ ] API-Dokumentation für LDAPManager
- [ ] User Guide (Benutzerhandbuch)
- [ ] Admin Guide (Administratorhandbuch)
- [ ] Installation Guide aktualisieren
- [ ] Code-Kommentare vervollständigen
- [ ] README.md erweitern

## Testing

### Unit Tests
- [ ] LDAPManager Tests
- [ ] Views Tests
- [ ] Forms Tests
- [ ] Models Tests
- [ ] Permissions Tests

### Integration Tests
- [ ] LDAP-Verbindung Tests
- [ ] User-Creation Flow
- [ ] Group-Management Flow
- [ ] Mail-Configuration Flow

### E2E Tests
- [ ] Login/Logout Flow
- [ ] Benutzer erstellen/bearbeiten/löschen
- [ ] Gruppen erstellen/bearbeiten/löschen
- [ ] Mail-Konfiguration
- [ ] Family Tree Navigation

## Deployment

- [ ] Production-Settings (DEBUG=False, ALLOWED_HOSTS, etc.)
- [ ] Environment Variables für sensible Daten
- [ ] HTTPS-Konfiguration
- [ ] Backup-Strategie für LDAP-Daten
- [ ] Monitoring und Alerting Setup
- [ ] Continuous Integration/Deployment (CI/CD)
- [ ] Docker-Container erstellen
- [ ] Nginx/Apache Reverse Proxy Konfiguration

## Bekannte Probleme

1. ~~**Login mit E-Mail**: IntegrityError bei Login mit E-Mail-Adresse~~ - ✅ BEHOBEN (2026-02-01)
2. ~~**Toast Close Button**: Close-Button war schwer sichtbar~~ - ✅ BEHOBEN (2026-02-01)
3. **LDAP-Verbindung**: Bei langen Idle-Zeiten können Verbindungen timeout - Auto-Reconnect verbessern
4. **Foto-Upload**: Große Bilder (>1MB) werden abgelehnt - besseres Feedback geben
5. **Search Performance**: Bei >1000 Benutzern wird Suche langsam - Pagination und Indexing
6. **Parent-Selection**: Dropdown wird unübersichtlich bei vielen Benutzern - Autocomplete hinzufügen
7. ~~**Mail-Domains im Dashboard**: Waren klickbar und verlinkten auf Benutzersuche statt Mail-Verwaltung~~ - ✅ BEHOBEN

## Backup & Recovery

### LDAP Backup
- [ ] **LDAP-Daten exportieren** (LDIF-Format)
- [ ] **Automatische Backups** (täglich, wöchentlich, monatlich)
- [ ] **LDAP-Daten importieren** (Restore-Funktion)
- [ ] **Inkrementelle Backups** (nur Änderungen seit letztem Backup)
- [ ] **Backup-Verschlüsselung** (AES-256)

### Datei-Backup
- [ ] **Hochgeladene Fotos sichern** (alle jpegPhoto-Attribute)
- [ ] **Datenbank-Backup** (SQLite-Datenbank mit Logs, Permissions, etc.)
- [ ] **Backup auf externen Speicher** (FTP, SFTP, S3, etc.)
- [ ] **Automatische Backup-Rotation** (alte Backups löschen)

### Restore-Funktionen
- [ ] **LDAP-Daten wiederherstellen** (aus LDIF-Datei)
- [ ] **Fotos wiederherstellen** (alle Benutzer-Fotos)
- [ ] **Selektives Restore** (nur bestimmte Benutzer/Gruppen)
- [ ] **Backup-Verifikation** (Integrität prüfen)

### Backup-Management
- [ ] **Backup-Dashboard** (Übersicht aller Backups)
- [ ] **Backup-History** (wann wurde was gesichert)
- [ ] **Backup-Download** (Backups herunterladen)
- [ ] **E-Mail-Benachrichtigungen** (bei erfolgreichen/fehlgeschlagenen Backups)

## Nice-to-Have Features

- [ ] Calendar Integration (Geburtstage, Veranstaltungen)
- [ ] Notification System (WebSocket für Echtzeit-Updates)
- [ ] Mobile App (React Native oder Flutter)
- [ ] Statistik-Dashboards mit Charts (Chart.js oder D3.js)
- [ ] Email-Templates verwalten
- [ ] SMS-Benachrichtigungen
- [ ] Mehrsprachigkeit (i18n)
- [ ] Accessibility Verbesserungen (ARIA, Screenreader)
- [ ] GraphQL API für externe Anwendungen
- [ ] Webhook Integration für externe Services

## Langfristige Ziele

- [ ] Migration zu Django 5.x
- [ ] Moderne Frontend-Framework Integration (React, Vue, Svelte)
- [ ] Microservices-Architektur erwägen
- [ ] Machine Learning für Anomalie-Erkennung
- [ ] Blockchain für Audit-Trail (optional)

---

**Stand:** 2026-04-04
**Version:** 1.1.0
**Maintainer:** Church Admin Team

**Letzte Aenderungen (2026-04-04):**
- Benutzer-Dashboard mit Familienverwaltung
- CAPTCHA fuer Passwort-Reset
- Mail-Verwaltung mit CRUD-Listen im Admin
- Editierbares Profil mit Geburtstag-Widget
- Deploy-Script mit DB-Schutz
- Passwort-Reset an private Mail (mailRoutingAddress)
- AppSettings fuer E-Mail-Konfiguration
