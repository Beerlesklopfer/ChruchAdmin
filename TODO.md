# Church Admin - TODO Liste

## Bugs

### Hohe Priorität
- [ ] **First login after setup**: LDAP-Verbindung automatisch beim ersten Login nach Setup erstellen

### Mittlere Priorität
- [ ] Passwort-Zurücksetzen für LDAP-Benutzer testen und verfeinern
- [ ] Fehlerbehandlung bei fehlgeschlagener LDAP-Verbindung verbessern
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

### Phase 8: Error Handling & Logging (Teilweise)
- [x] Custom Exceptions definiert
- [x] Logging in LDAPManager
- [x] Django Messages für User Feedback
- [ ] Admin-Benachrichtigungen bei kritischen Fehlern
- [ ] Detaillierte Error-Pages

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

1. **LDAP-Verbindung**: Bei langen Idle-Zeiten können Verbindungen timeout - Auto-Reconnect verbessern
2. **Foto-Upload**: Große Bilder (>1MB) werden abgelehnt - besseres Feedback geben
3. **Search Performance**: Bei >1000 Benutzern wird Suche langsam - Pagination und Indexing
4. **Parent-Selection**: Dropdown wird unübersichtlich bei vielen Benutzern - Autocomplete hinzufügen
5. **Mail-Domains im Dashboard**: ✅ BEHOBEN - Waren klickbar und verlinkten auf Benutzersuche statt Mail-Verwaltung

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

**Stand:** 2026-02-01
**Version:** 1.0
**Maintainer:** Church Admin Team
