# LDAP-Schemas fuer ChurchAdmin

## Installationsreihenfolge

Die Schemas muessen in dieser Reihenfolge installiert werden:

```bash
# 1. POSIX-Accounts (uidNumber, gidNumber, homeDirectory)
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/rfc2307bis.ldif

# 2. Postfix Mail-Schema (mailExtension, groupMail, mailDomain)
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/postfix.ldif

# 3. Erweiterte Personendaten (birthDate, familyRole, Social Media)
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/postModernalPerson.ldif

# 4. Nextcloud-Integration (nextCloudEnabled, nextCloudQuota)
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/nextcloud.ldif

# 5. ChurchAdmin-Erweiterungen
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_familyRole.ldif
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_familyRole_step2.ldif
sudo ldapmodify -Y EXTERNAL -H ldapi:/// -f ldap/schema_extend_accountDisabled.ldif
```

## Schema-Uebersicht

| Datei | ObjectClasses | Attribute |
|-------|--------------|-----------|
| `rfc2307bis.ldif` | posixAccount, posixGroup | uidNumber, gidNumber, homeDirectory, loginShell |
| `postfix.ldif` | mailExtension, groupMail, mailRecipient, mailDomain | mailRoutingAddress, mailAliasAddress, mailQuota, mailGroup, mailDomainName |
| `postModernalPerson.ldif` | postModernalPerson | birthDate, maidName, civilState, sex, Social Media (YouTube, Instagram, etc.) |
| `nextcloud.ldif` | nextCloudUser, nextCloudGroup | nextCloudEnabled, nextCloudQuota |
| `schema_extend_familyRole.ldif` | — | familyRole (head/spouse/child/dependent) |
| `schema_extend_accountDisabled.ldif` | — | accountDisabled (TRUE/FALSE) |

## Pruefung

```bash
# Installierte Schemas anzeigen
sudo ldapsearch -Y EXTERNAL -H ldapi:/// -b "cn=schema,cn=config" "(objectClass=olcSchemaConfig)" cn -LLL

# Bestimmtes Schema pruefen
sudo ldapsearch -Y EXTERNAL -H ldapi:/// -b "cn=schema,cn=config" "(cn=*postfix*)" -LLL
```
