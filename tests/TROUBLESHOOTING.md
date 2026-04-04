# Troubleshooting Guide - ChurchAdmin

## LDAP-Probleme

### Benutzer kann sich nicht anmelden
1. **Account deaktiviert?** Im Admin-Editor pruefen: `accountDisabled = TRUE`
2. **Case-Sensitivity:** LDAP CN ist case-insensitive, `get_user()` nutzt `SCOPE_SUBTREE` mit Filter
3. **IntegrityError:** Django-User existiert bereits mit anderem Username → Workaround-Login-Pfad aktiv
4. **Registrierung pending/rejected:** `RegistrationRequest`-Status blockiert Login

```bash
# LDAP-User pruefen
ldapsearch -x -H ldaps://ldap.example-church.de -b "ou=Users,dc=example-church,dc=de" "(cn=Username)"

# accountDisabled pruefen
ldapsearch -x -H ldaps://ldap.example-church.de -b "ou=Users,dc=example-church,dc=de" "(cn=Username)" accountDisabled
```

### LDAP-Verbindung langsam
- Thread-local Connection Caching ist aktiv (`LDAPManager` mit `threading.local()`)
- Idle-Timeout: Bei langen Pausen kann die Verbindung verloren gehen → Auto-Reconnect

### Schema-Fehler: "attribute not allowed"
- Benutzer hat nicht die richtige objectClass
- `mailAliasEnabled` braucht `mailExtension` objectClass
- `accountDisabled` braucht `postModernalPerson` objectClass

```bash
# ObjectClasses eines Users pruefen
ldapsearch -x -H ldaps://ldap.example-church.de -b "ou=Users,dc=example-church,dc=de" "(cn=Username)" objectClass
```

### posixAccount requires uidNumber
- Beim Erstellen: `_next_uid_number()` generiert automatisch die naechste UID
- Bei bestehenden Usern ohne uidNumber: manuell setzen oder User neu erstellen

## Django-Probleme

### TemplateSyntaxError
- `{{` und `}}` in Templates werden als Django-Variablen interpretiert
- Fuer Platzhalter `[[vorname]]` statt `{{vorname}}` verwenden
- Bei Bedarf `{% verbatim %}...{% endverbatim %}` nutzen

### Decorators an falscher Funktion
- `@login_required` und `@user_passes_test` kleben an der naechsten `def`
- Hilfsfunktionen (z.B. `_get_user_consents`) OHNE Decorator definieren
- Decorator gehoert immer direkt vor den View, keine Leerzeile dazwischen

### Binaere Attribute (jpegPhoto) kaputt
- `decode_attribute()` dekodiert ALLE Attribute als UTF-8
- Binaere Attribute (`jpegPhoto`, `userCertificate`) muessen uebersprungen werden
- Siehe `BINARY_ATTRS` Set in `get_user()` und `list_users()`

### Django-User existiert nicht (Kind/Ehepartner)
- Kinder die nie eingeloggt waren haben keinen Django-User
- `get_or_create_django_user(cn)` erstellt den User aus LDAP-Daten
- Wird bei Consent-Aenderungen und Familien-Edit automatisch aufgerufen

## Mail-Probleme

### E-Mail wird nicht versendet
```bash
# Postfix-Log pruefen
grep "from=<" /var/log/mail.log | tail -10

# Django-Einstellungen pruefen
python main/manage.py shell -c "from django.conf import settings; print(settings.EMAIL_HOST, settings.DEFAULT_FROM_EMAIL)"
```

### LDAP-Fehler bei E-Mail: "Invalid syntax mail value"
- CN mit Sonderzeichen (Umlaute) erzeugt ungueltige E-Mail-Adressen
- `_sanitize()` Funktion ersetzt Umlaute und entfernt Akzente

### Opt-out-Link funktioniert nicht
- Token abgelaufen (max 1 Jahr)
- `signing.loads()` mit `salt='email-optout'` pruefen
- User muss in Django-DB existieren (`get_or_create_django_user`)

## Deployment-Probleme

### collectstatic PermissionError
- `chown www-data` muss VOR `collectstatic` laufen
- deploy.sh setzt Berechtigungen in der richtigen Reihenfolge

### DB wird beim Deploy ueberschrieben
- `db.sqlite3` ist in `--exclude` von rsync
- NIEMALS die Produktions-DB aus dem Repo deployen

### Service startet nicht
```bash
# Status pruefen
systemctl status churchadmin
journalctl -u churchadmin -n 50 --no-pager

# Socket pruefen
systemctl status churchadmin.socket
ls -la /run/churchadmin/
```

### TinyMCE API-Key Fehler
- TinyMCE ist lokal installiert unter `static/vendor/tinymce/`
- `license_key: 'gpl'` in der TinyMCE-Konfiguration
- NICHT die CDN-Version mit API-Key verwenden

## Backup-Probleme

### slapcat Permission denied
```bash
# sudoers pruefen
cat /etc/sudoers.d/churchadmin-slapcat
# Sollte enthalten: www-data ALL=(root) NOPASSWD: /usr/sbin/slapcat

# Manuell testen
sudo slapcat -n 0 | head
```

## Nuetzliche Befehle

```bash
# Django-Check
python main/manage.py check

# LDAP-Backup
python main/manage.py backup_ldap --type=full

# Mail-Vorlagen aktualisieren
python main/manage.py seed_templates

# Shell
python main/manage.py shell

# Benutzer-Consents pruefen
python main/manage.py shell -c "
from privacy.models import ConsentLog
for c in ConsentLog.objects.filter(user__username='Max.Mustermann').order_by('-timestamp')[:5]:
    print(f'{c.consent_type}: {c.granted} ({c.timestamp})')
"

# AppSettings pruefen
python main/manage.py shell -c "
from authapp.models import AppSettings
for s in AppSettings.objects.all():
    print(f'{s.key} = {s.value}')
"
```
