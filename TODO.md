# Church Admin - TODO Liste

## Naechste Schritte (Empfohlene Prioritaet)

### Sofort (Hohe Prioritaet)
1. **Gruppen-Detail-Ansicht** - Vollstaendige CRUD-Operationen fuer Gruppen
2. **Bulk-Operationen** - Mehrere Benutzer gleichzeitig bearbeiten
3. **Family Tree Visualisierung** - Interaktiver Baum fuer Familien-Hierarchie

### Kurzfristig
1. **Testing** - Unit Tests fuer LDAPManager und Views
2. **Documentation** - README.md erweitern mit Setup-Anleitung
3. **Security** - Two-Factor Authentication (2FA)

### Mittelfristig
1. **Verschluesselte Notizen (Phase 11)** - Seelsorge-Notizen fuer Pastor/Aelteste (Benutzer liest eigene Eintraege)

---

## Erledigte Aufgaben (2026-04-04)

### DSGVO-Compliance (Phase 12) ✅
- [x] **Privacy-App**: Eigene Django-App mit PrivacyPolicy, LegalPage, ConsentLog, DeletionRequest
- [x] **Datenschutzerklaerung**: Oeffentliche Seite, versioniert, editierbar im Admin
- [x] **Impressum**: Editierbar im Admin (LegalPage Model), Default per Data-Migration
- [x] **DSGVO-Auskunftsseite**: Alle LDAP/Django-Daten, Gruppen, Einwilligungen (/datenschutz/my-data/)
- [x] **Datenexport**: JSON-Download aller eigenen Daten
- [x] **Einwilligungsverwaltung**: Opt-out-Verfahren (Standard=erteilt), erteilen/widerrufen mit Protokoll
- [x] **Consent-Typen**: Datenschutzerklaerung, Datenverarbeitung, E-Mail-Kommunikation, Gemeindeliste
- [x] **Gemeindeliste-Consent**: Widerruf blendet User in Dashboard und PDF-Export aus (rekursiv fuer Familie)
- [x] **Datenverarbeitung-Widerruf**: Warndialog + automatischer Loeschantrag + Admin-Benachrichtigung
- [x] **Recht auf Vergessenwerden**: Loeschantrag mit Begruendung und Admin-Email
- [x] **Familien-Consent**: Oberhaupt verwaltet Consents fuer alle Familienmitglieder
- [x] **Ab 16 selbstverwaltet**: Kinder ab 16 koennen Consents auch selbst verwalten (Hinweis im UI)
- [x] **DSGVO im Admin-Editor**: Consent-Toggles (Schalter) im Benutzer-Edit-Modal
- [x] **DSGVO im Familien-Editor**: Consent-Toggles mit Datenschutzerklaerung-Link
- [x] **DSGVO-Checkbox bei Registrierung**: Pflichtfeld mit Link zur Datenschutzerklaerung
- [x] **get_or_create_django_user()**: Zentrale Funktion, erstellt Django-User aus LDAP bei Bedarf
- [x] **Footer**: Impressum + Datenschutz Links
- [x] **User-Menue**: "Meine Daten (DSGVO)" Link

### Massen-E-Mail (Phase 13) ✅
- [x] **Mailing-App**: Eigene Django-App mit MailCampaign, MailLog, MailTemplate Models
- [x] **TinyMCE WYSIWYG-Editor**: Selbst gehostet (kein API-Key), fuer Body und Footer
- [x] **Empfaenger-Checkboxen**: Mitglieder/Besucher/Angehoerige/Gaeste/Gruppen/Manuell (Mehrfachauswahl)
- [x] **Personalisierung**: [[vorname]], [[nachname]], [[name]] Platzhalter
- [x] **Vorlagen-System**: seed_templates Management Command, 4 Vorlagen (Gemeindebrief, System, Willkommen Sie/Du)
- [x] **DSGVO-Hinweise in Vorlagen**: Gemeindeliste-Opt-out, Familien-Consent, Datenschutz-Verwaltung
- [x] **Vorschau**: Empfaengerliste mit Anzahl, Mail-Vorschau
- [x] **Test-Mail**: An sich selbst senden mit Opt-out-Link
- [x] **Versand mit Bestaetigung**: Bestaetigungsdialog vor Massenversand
- [x] **Versandprotokoll**: Pro Empfaenger (zugestellt/fehlgeschlagen)
- [x] **Opt-out-Link**: Signierter Abmelde-Link in jeder Mail (1 Jahr gueltig, ohne Login)
- [x] **Opt-out-Seite**: Bestaetigungsmeldung mit Anleitung zur Wiederanmeldung
- [x] **Opt-out-Pruefung**: Widerrufene Empfaenger werden beim Versand uebersprungen
- [x] **Editierbarer Footer**: Eigene TinyMCE-Instanz, DSGVO-Default aus AppSettings
- [x] **Kampagnen**: Duplizieren, loeschen, bearbeiten (nur Entwuerfe)
- [x] **Berechtigung**: send_massmail (getrennt von manage_mail)
- [x] **Tools-Menue**: Berechtigungsgesteuert (can_send_massmail, can_export_members)

### Konfiguration ✅
- [x] **Gemeindename konfigurierbar**: church_name, church_domain, church_address aus AppSettings
- [x] **Ansprechpersonen**: church_contact_person, privacy_contact_person
- [x] **Context Processor**: church_settings stellt alle Werte in Templates bereit
- [x] **Berechtigungsmatrix dynamisch**: Liest aus PermissionMapping.PERMISSION_CHOICES (keine hardcoded Listen)
- [x] **Status-Dropdown im Benutzer-Editor**: Mitglied/Besucher/Gast mit Gruppenmitgliedschaft
- [x] **familyRole dependent**: Angehoeriger als neue Familienrolle

### Account-Deaktivierung & Sicherheit ✅
- [x] **accountDisabled LDAP-Attribut**: Neues Attribut im postModernalPerson-Schema (OID 1.3.6.1.4.1.99999.16)
- [x] **Login-Block fuer deaktivierte Accounts**: Pruefung VOR login() in beiden Login-Pfaden
- [x] **Warn-Email an Admins**: Bei Login-Versuch mit deaktiviertem Account (mit IP, Zeitstempel)
- [x] **Admin-Toggle**: accountDisabled im Benutzer-Edit-Dialog schaltbar
- [x] **Status in Benutzerliste**: Deaktivierte Accounts sichtbar markiert

### Benutzer-CRUD komplett ✅
- [x] **Benutzer erstellen**: Mit Auto-CN-Generierung, Passwort, posixAccount-Attributen
- [x] **Benutzer bearbeiten**: Alle Attribute inkl. familyRole, accountDisabled, Parent-Wechsel (Heirat)
- [x] **Benutzer loeschen**: Mit Bestaetigungsdialog, Familien-Loesch-Option, Django-User-Cleanup
- [x] **Loeschungs-Email**: Benachrichtigung an geloeschten Benutzer (externe Mail-Adresse)
- [x] **Foto-Upload**: jpegPhoto im LDAP

### Self-Registration (Phase 9) ✅
- [x] **Registrierungsformular**: Oeffentlich unter /register/ mit CAPTCHA und Honeypot
- [x] **E-Mail-Verifizierung**: Bestaetigung per Link bevor Anfrage ins Admin-Dashboard kommt
- [x] **RegistrationRequest Model**: Status-Flow: unverified → pending → approved/rejected
- [x] **Admin-Genehmigungs-Dashboard**: Liste offener Anfragen mit Approve/Reject/Delete
- [x] **Automatische LDAP-User-Erstellung**: Bei Genehmigung mit Zufalls-Passwort und Willkommens-Mail
- [x] **Ablehnungs-Mail**: HTML-Email mit optionaler Begruendung
- [x] **Rate Limiting**: Max 3 Anfragen pro IP/Stunde
- [x] **Login-Pruefung**: Abgelehnte/ausstehende Registrierungen blockieren Login
- [x] **Benachrichtigung an Admins**: Alle User mit manage_registrations-Berechtigung werden informiert
- [x] **Username-Sanitisierung**: Umlaute/Akzente werden automatisch ersetzt, Unique-Suffix bei Duplikaten

### LDAP-Schema-Erweiterungen ✅
- [x] **familyRole Attribut**: head/spouse/child/dependent (OID 1.3.6.1.4.1.99999.15)
- [x] **accountDisabled Attribut**: TRUE/FALSE (OID 1.3.6.1.4.1.99999.16)
- [x] **NISplus-Schema**: posixAccount fuer uidNumber, gidNumber, homeDirectory, loginShell
- [x] **Auto-uidNumber**: Naechste freie UID wird automatisch vergeben

### Familienverwaltung ✅
- [x] **Family Tree**: Familien-Uebersicht mit Oberhaupt, Ehepartner, Kindern
- [x] **familyRole-basiert**: Keine altersbasierte Erkennung, explizite Rollen im LDAP
- [x] **Vaeter-Verwaltung**: Familienoberhaeupter koennen Kinder bearbeiten
- [x] **Ehepartner-Anzeige**: Neben Oberhaupt in Family-Tree
- [x] **Heirats-Workflow**: familyRole=spouse + parent_cn → LDAP move_user + optionale Namensaenderung
- [x] **Kinder hinzufuegen**: Admin kann Kinder unter Eltern erstellen
- [x] **Gemeindeliste**: Familien-basiert mit Rollen-Icons (PDF-Export)

### Benutzer-Dashboard & Navigation ✅
- [x] **Benutzer-Dashboard**: Persoenliches Dashboard fuer alle Benutzer (/dashboard/)
- [x] **Familienverwaltung**: Vaeter verwalten, Mitglieder sehen (read-only)
- [x] **Gemeindeliste im Dashboard**: Tabelle mit Familien
- [x] **Login-Redirect**: Admins → Admin-Dashboard, normale User → Benutzer-Dashboard, next-Parameter respektiert
- [x] **Navigation**: LDAP-Verwaltung nur fuer Admins, "Mein Bereich" fuer alle
- [x] **Context Processor**: is_ldap_admin, can_manage_ldap, can_send_massmail, can_export_members, show_tools_menu

### Berechtigungssystem ✅
- [x] **PermissionMapping Model**: Gruppen-basierte Berechtigungen
- [x] **Berechtigungsmatrix**: Admin-UI zum Zuweisen von Rechten pro Gruppe
- [x] **Berechtigungen**: view_members, edit_members, manage_mail, export_members, manage_registrations, send_massmail
- [x] **Rollen-Checkboxen**: Pastor, Aeltester, Diakon, Sekretariat im Benutzer-Dialog

### CAPTCHA & Passwort-Reset ✅
- [x] **CAPTCHA**: django-simple-captcha fuer Passwort-Reset und Registrierung
- [x] **Passwort-Reset an private Mail**: Reset-Mail geht an erste externe mailRoutingAddress
- [x] **Suche per privater Mail**: Funktioniert mit Username, Org-Mail oder privater Mail
- [x] **LDAP change_password Fix**: Bytes-Encoding fuer SSHA-Passwort-Hash

### Mail-Verwaltung ✅
- [x] **Mail-Attribute im Admin**: mail, mailRoutingAddress, mailAliasAddress, mailQuota, mailAliasEnabled, mailRoutingEnabled
- [x] **CRUD-Listen**: Dynamische Add/Remove fuer Multi-Value-Mail-Attribute
- [x] **Mail-Sub-Template**: Wiederverwendbar fuer E-Mail-Listen
- [x] **AppSettings**: SMTP, Absender, Reply-To konfigurierbar
- [x] **mailExtension objectClass**: Automatische Pruefung vor Mail-Attribut-Aenderungen

### Profil & Benutzerdaten ✅
- [x] **Editierbares Profil**: Name, Telefon, Mobil, Anschrift, Geburtstag
- [x] **Geburtstag-Widget**: HTML5 date-Input mit LDAP generalizedTime-Konvertierung
- [x] **Organisations-Email read-only**: Mail und Rolle nur durch Admin aenderbar
- [x] **Postanschrift**: postalAddress im LDAP

### Gemeindeliste & Export ✅
- [x] **PDF-Export**: Landscape A4 mit DejaVuSans (Unicode-Support)
- [x] **Spalten**: Name, Email, Telefon, Mobil, Anschrift, Geburtstag, Gruppen
- [x] **Rollen-Icons**: ★ Oberhaupt, ♥ Ehepartner, ↳ Kind
- [x] **Sortierung**: Nach Nachname
- [x] **Header auf jeder Seite**: Mit Datum und Seitenzahl
- [x] **Filter**: Mitglieder (inkl. Familienangehoerige), alle, Besucher, Gaeste
- [x] **Alle Mitglieder duerfen exportieren**: export_members-Berechtigung
- [x] **DSGVO-Consent-Pruefung**: Benutzer mit widerrufener Gemeindeliste-Sichtbarkeit ausgeblendet

### Backup & Recovery ✅
- [x] **LDAP-Backup**: Django Management Command backup_ldap
- [x] **Backup-Dashboard**: Uebersicht aller Backups mit Download/Delete/Restore
- [x] **Bareos-Integration**: LDAP-Plugin fuer automatische Backups
- [x] **LDAPBackup Model**: Tracking von Backups in Django-DB

### Performance ✅
- [x] **Thread-local Connection Caching**: LDAP-Seitenlade von 15s auf 5s reduziert
- [x] **Case-insensitive User-Suche**: get_user() mit SCOPE_SUBTREE statt SCOPE_BASE
- [x] **Pagination**: Auswaehlbare Seitengroesse (10/20/30/40/50 pro Seite)

### Deployment ✅
- [x] **Deploy-Script**: deploy.sh mit rsync, venv, migrate, collectstatic, seed_templates, Service-Restart
- [x] **DB-Schutz**: db.sqlite3 wird beim Deploy nicht ueberschrieben
- [x] **Default-Berechtigungen**: view_members + export_members fuer Mitglieder bei Deploy
- [x] **Default-AppSettings**: church_name, church_address, etc. bei Erstinstallation
- [x] **Gunicorn + systemd**: Socket-Activation
- [x] **nginx Reverse Proxy**: Static Files, SSL

### E-Mail-Vorlagen ✅
- [x] **registration_verify.html**: Verifizierungs-Link (HTML)
- [x] **registration_approved.html**: Willkommens-Mail mit Zugangsdaten, DSGVO-Hinweisen (HTML)
- [x] **registration_rejected.html**: Ablehnungs-Mail mit Begruendung (HTML)
- [x] **account_deleted.html**: Benachrichtigung bei Konto-Loeschung (HTML)
- [x] **disabled_login_attempt.html**: Sicherheitshinweis an Admins (HTML)
- [x] **optout_result.html**: Opt-out-Bestaetigungsseite mit Wiederanmeldeanleitung

---

## Erledigte Aufgaben (2026-02-01)

### Login & Authentifizierung ✅
- [x] **Email-Login**: Benutzer koennen sich mit E-Mail statt Username anmelden
- [x] **Email-zu-Username-Normalisierung**: Automatische LDAP-Lookup fuer cn
- [x] **IntegrityError-Handling**: Robuste Fehlerbehandlung bei Login

### Email-System ✅
- [x] **EmailTemplate Model**: Editierbare Vorlagen im Admin
- [x] **Willkommens-Email**: Automatisch bei Aufnahme in Mitglieder-Gruppe

### UI/UX ✅
- [x] **Toast-Notifications**: Church CI Styling
- [x] **Status-basierte Filterung**: Mitglieder, Besucher, Gaeste, Ehepartner, Angehoerige
- [x] **Live-Suche**: Debounced in Benutzer- und Mitgliederverwaltung
- [x] **Autoconfig**: iOS Mail-Konfiguration

---

## Offene Features

### Phase 5: Gruppenverwaltung (Teilweise)
- [x] Gruppen-Liste mit hierarchischer Einrueckung
- [x] Mitglieder hinzufuegen/entfernen
- [ ] Gruppen-Detail-Ansicht mit Mitgliedern
- [ ] Gruppe erstellen (mit Parent-Gruppe)
- [ ] Gruppe bearbeiten
- [ ] Gruppe loeschen
- [ ] Gruppen-Baum Visualisierung

### Phase 6: Mail-Verwaltung (Teilweise)
- [x] Benutzer-Mail-Attribute editierbar (mail, mailRouting, mailAlias, Quota)
- [ ] Mail-Uebersicht (alle konfigurierten Benutzer/Gruppen)
- [ ] Mail-Domains verwalten
- [ ] Gruppen-Mail-Adressen konfigurieren
- [ ] Bulk-Mail-Konfiguration

### Phase 10: Todo & Bug Tracking
- [ ] Internes Tracking-System

### Phase 11: Verschluesselte Notizen fuer Pastor/Aelteste
- [ ] PersonNote Model mit AES-256-Verschluesselung
- [ ] Zugriffskontrolle: Pastor/Aelteste lesen alle, Benutzer liest eigene Eintraege
- [ ] Audit-Log

---

## Offene Bugs

### Mittlere Prioritaet
- [ ] **First login after setup**: LDAP-Verbindung automatisch beim ersten Login erstellen
- [ ] **Foto-Upload**: Grosse Bilder (>1MB) besser validieren und Feedback geben

### Niedrige Prioritaet
- [ ] **Responsive Design**: Mobile Geraete optimieren
- [ ] **LDAP Idle-Timeout**: Auto-Reconnect bei langen Idle-Zeiten verbessern

---

## Nice-to-Have Features

- [ ] Two-Factor Authentication (2FA)
- [ ] Calendar Integration (Geburtstage, Veranstaltungen)
- [ ] Dark Mode Toggle
- [ ] Keyboard Shortcuts (Strg+K fuer Schnellsuche)
- [ ] Notification System (WebSocket)
- [ ] CSV/Excel Export fuer Benutzer/Gruppen
- [ ] Mehrsprachigkeit (i18n)
- [ ] Accessibility (ARIA, Screenreader)

---

**Stand:** 2026-04-05
**Version:** 2.0.0
**Maintainer:** Joerg Bernau
