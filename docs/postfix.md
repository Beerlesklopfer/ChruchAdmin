# Postfix + LDAP Konfiguration fuer ChurchAdmin

## Uebersicht

ChurchAdmin nutzt Postfix als Mail Transfer Agent (MTA) in Kombination mit:
- **OpenLDAP** fuer Benutzer- und Mailbox-Verwaltung
- **Dovecot** fuer IMAP/LMTP (Mailbox-Zustellung)
- **OpenDKIM** fuer E-Mail-Signierung
- **Let's Encrypt** fuer TLS-Zertifikate

```
                    ┌──────────────┐
  Internet ──────►  │   Postfix    │
                    │  (SMTP/TLS)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  LDAP    │ │ Dovecot  │ │ OpenDKIM │
        │ (Lookup) │ │ (LMTP)   │ │ (Sign)   │
        └──────────┘ └──────────┘ └──────────┘
```

## Django E-Mail-Einstellungen

In `main/settings.py`:

```python
EMAIL_HOST = 'example-church.de'  # Postfix auf dem gleichen Server
EMAIL_PORT = 25                        # Lokaler SMTP (kein Auth noetig)
DEFAULT_FROM_EMAIL = 'webmaster@example-church.de'
SERVER_EMAIL = 'webmaster@example-church.de'
```

Django sendet E-Mails direkt an den lokalen Postfix. Kein SMTP-Passwort noetig, da localhost vertraut wird (`mynetworks`).

## Postfix Hauptkonfiguration

`/etc/postfix/main.cf`:

```ini
# Hostname und Domain
myhostname = mail.example-church.de
mydomain = example-church.de
myorigin = /etc/mailname

# Nur localhost als Ziel (alles andere ist virtual)
mydestination = localhost, localhost.localdomain

# Vertrauenswuerdige Netzwerke (localhost + Server-IP)
mynetworks = 127.0.0.0/8 [::1]/128 [Server-IPv6]/128 Server-IPv4

# Dovecot fuer Mailbox-Zustellung
mailbox_transport = lmtp:unix:private/dovecot-lmtp
virtual_transport = lmtp:unix:private/dovecot-lmtp

# TLS (Let's Encrypt)
smtpd_tls_key_file  = /etc/letsencrypt/live/example-church.de/privkey.pem
smtpd_tls_cert_file = /etc/letsencrypt/live/example-church.de/fullchain.pem
smtpd_tls_security_level = may
smtp_tls_security_level = may

# SASL Authentifizierung (Dovecot)
smtpd_sasl_type = dovecot
smtpd_sasl_path = private/auth
smtpd_sasl_auth_enable = yes
smtpd_sasl_security_options = noanonymous

# OpenDKIM
milter_default_action = accept
milter_protocol = 6
smtpd_milters = unix:opendkim/opendkim.sock
non_smtpd_milters = unix:opendkim/opendkim.sock

# LDAP-Anbindung
smtpd_sender_login_maps = ldap:/etc/postfix/ldap/sender_login_maps.cf
local_recipient_maps    = ldap:/etc/postfix/ldap/mbox_recipient_maps.cf
virtual_alias_maps      = hash:/etc/aliases hash:/etc/postfix/virtual ldap:/etc/postfix/ldap/virtual_forward_maps.cf ldap:/etc/postfix/ldap/virtual_group_maps.cf
virtual_mailbox_domains = ldap:/etc/postfix/ldap/virtual_mailbox_domains.cf

# Keine Groessenbeschraenkung
mailbox_size_limit = 0
inet_interfaces = all
```

## LDAP-Lookup-Konfigurationen

Alle Dateien unter `/etc/postfix/ldap/`:

### sender_login_maps.cf
Prueft ob ein Benutzer berechtigt ist, unter einer bestimmten Adresse zu senden.

```ini
server_host = ldaps://ldap.example-church.de
version = 3
bind = yes
bind_dn = cn=admin,dc=example-church,dc=de
bind_pw = LDAP_ADMIN_PASSWORT

search_base = ou=Users,dc=example-church,dc=de
scope = sub
query_filter = (mail=%s)
result_attribute = cn
```

### virtual_forward_maps.cf
Leitet E-Mails an die `mailRoutingAddress` weiter (private Adresse).

```ini
server_host = ldaps://ldap.example-church.de
version = 3
bind = yes
bind_dn = cn=admin,dc=example-church,dc=de
bind_pw = LDAP_ADMIN_PASSWORT

search_base = ou=Users,dc=example-church,dc=de
scope = sub
query_filter = (&(mail=%s)(mailRoutingEnabled=TRUE))
result_attribute = mailRoutingAddress
```

### virtual_group_maps.cf
Loest Gruppen-E-Mail-Adressen auf (z.B. leitung@example-church.de).

```ini
server_host = ldaps://ldap.example-church.de
version = 3
bind = yes
bind_dn = cn=admin,dc=example-church,dc=de
bind_pw = LDAP_ADMIN_PASSWORT

search_base = ou=Groups,dc=example-church,dc=de
scope = sub
query_filter = (&(objectClass=groupMail)(mailGroup=%s))
result_attribute = mailRoutingAddress
```

### virtual_mailbox_domains.cf
Bestimmt welche Domains als "virtual" gelten.

```ini
server_host = ldaps://ldap.example-church.de
version = 3
bind = yes
bind_dn = cn=admin,dc=example-church,dc=de
bind_pw = LDAP_ADMIN_PASSWORT

search_base = dc=example-church,dc=de
scope = sub
query_filter = (mailDomainName=%s)
result_attribute = mailDomainName
```

## Virtuelle Aliase

`/etc/postfix/virtual` — statische Weiterleitungen:

```
# Primaere Domain
info@example-church.de          pastor@example-church.de
kontakt@example-church.de       pastor@example-church.de
webmaster@example-church.de     admin@example-church.de
postmaster@example-church.de    admin@example-church.de
abuse@example-church.de         admin@example-church.de
```

Nach Aenderungen:
```bash
sudo postmap /etc/postfix/virtual
sudo systemctl reload postfix
```

## LDAP-Schema fuer Mail

Das `postfix.ldif` Schema (aus `ldap-for-churches`) definiert:

| ObjectClass | Beschreibung |
|-------------|-------------|
| `mailExtension` | Benutzer-Mailbox (mailRoutingAddress, mailAliasAddress, mailQuota) |
| `groupMail` | Gruppen-E-Mail (mailGroup) |
| `mailRecipient` | Empfaenger (mail + mailRoutingAddress) |
| `mailDomain` | E-Mail-Domain (mailDomainName) |

| Attribut | Beschreibung |
|----------|-------------|
| `mailRoutingEnabled` | Weiterleitung aktiv (TRUE/FALSE) |
| `mailAliasEnabled` | Alias aktiv (TRUE/FALSE) |
| `mailQuota` | Postfach-Groesse |
| `mailRoutingAddress` | Private E-Mail (Weiterleitung) |
| `mailAliasAddress` | Alias-Adressen |
| `mailGroup` | Gruppen-E-Mail-Adresse |

## Mailflow

### Eingehend
1. E-Mail an `Vorname.Nachname@example-church.de`
2. Postfix prueft `virtual_mailbox_domains` → Domain bekannt
3. Postfix prueft `virtual_forward_maps` → `mailRoutingEnabled=TRUE`?
4. Wenn ja: Weiterleitung an `mailRoutingAddress` (z.B. private GMail)
5. Wenn nein: Zustellung an Dovecot (LMTP) → lokale Mailbox

### Ausgehend (ChurchAdmin)
1. Django sendet E-Mail an `localhost:25`
2. Postfix signiert mit OpenDKIM
3. Postfix stellt zu (lokal oder remote)

### Massen-E-Mail (ChurchAdmin)
1. ChurchAdmin sammelt Empfaenger aus LDAP
2. Opt-out-Pruefung: Benutzer mit widerrufener E-Mail-Einwilligung uebersprungen
3. Pro Empfaenger: Personalisierung + Opt-out-Link
4. Versand ueber lokalen Postfix
5. Protokollierung in MailLog (zugestellt/fehlgeschlagen)

## Fehlerbehebung

```bash
# Mail-Queue anzeigen
mailq

# Log pruefen
tail -f /var/log/mail.log

# Postfix-Konfiguration testen
postfix check

# LDAP-Lookup testen
postmap -q "Vorname.Nachname@example-church.de" ldap:/etc/postfix/ldap/virtual_forward_maps.cf

# Postfix neu laden
sudo systemctl reload postfix
```

## Verwandte Dateien

| Datei | Beschreibung |
|-------|-------------|
| `/etc/postfix/main.cf` | Postfix-Hauptkonfiguration |
| `/etc/postfix/virtual` | Statische Aliase |
| `/etc/postfix/ldap/*.cf` | LDAP-Lookup-Konfigurationen |
| `/etc/dovecot/` | Dovecot IMAP/LMTP-Konfiguration |
| `/etc/opendkim/` | DKIM-Signierung |
| `ldap-for-churches` | LDAP-Schema-Paket (postfix.ldif, postModernalPerson.ldif) |
