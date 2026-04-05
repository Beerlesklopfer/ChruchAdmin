"""
LDAP Verbindungstest und Troubleshooting
=========================================

Dieses Skript hilft bei der Diagnose von LDAP-Verbindungsproblemen.
"""

import ldap
import sys

# LDAP-Konfiguration
LDAP_SERVER = 'ldaps://ldap.bibelgemeinde-lage.de'
BIND_DN = 'cn=admin,dc=bibelgemeinde-lage,dc=de'
BIND_PASSWORD = 'REDACTED'

def test_ldap_connection():
    """Testet die LDAP-Verbindung mit verschiedenen Methoden"""

    print("=" * 60)
    print("LDAP Verbindungstest")
    print("=" * 60)
    print(f"Server: {LDAP_SERVER}")
    print(f"Bind DN: {BIND_DN}")
    print()

    # Test 1: Verbindung ohne SSL-Validierung
    print("Test 1: Verbindung mit deaktivierter SSL-Validierung...")
    try:
        # SSL-Zertifikat-Validierung deaktivieren (nur für Entwicklung!)
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

        conn = ldap.initialize(LDAP_SERVER)
        conn.set_option(ldap.OPT_REFERRALS, 0)
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        conn.set_option(ldap.OPT_X_TLS_NEWCTX, 0)

        conn.simple_bind_s(BIND_DN, BIND_PASSWORD)
        print("✅ Verbindung erfolgreich!")

        # Teste eine einfache Suche
        result = conn.search_s(
            "dc=bibelgemeinde-lage,dc=de",
            ldap.SCOPE_BASE,
            "(objectClass=*)"
        )
        print(f"✅ LDAP-Server antwortet korrekt")
        print(f"   Base DN: {result[0][0]}")

        conn.unbind_s()
        return True

    except ldap.SERVER_DOWN as e:
        print(f"❌ Server nicht erreichbar: {e}")
        print(f"   Info: {e.args[0].get('info', 'Keine Details')}")
        return False
    except ldap.INVALID_CREDENTIALS:
        print("❌ Ungültige Anmeldedaten")
        return False
    except ldap.LDAPError as e:
        print(f"❌ LDAP-Fehler: {e}")
        return False
    except Exception as e:
        print(f"❌ Allgemeiner Fehler: {e}")
        return False

def test_alternative_servers():
    """Testet alternative LDAP-Server (localhost)"""

    print("\n" + "=" * 60)
    print("Test alternativer Server")
    print("=" * 60)

    # Test localhost ohne SSL
    alt_servers = [
        ('ldap://localhost:389', 'Lokaler LDAP (unverschlüsselt)'),
        ('ldap://127.0.0.1:389', 'Lokaler LDAP via IP'),
    ]

    for server, description in alt_servers:
        print(f"\nTeste {description}: {server}")
        try:
            conn = ldap.initialize(server)
            conn.set_option(ldap.OPT_REFERRALS, 0)
            conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)

            # Versuche anonymen Bind
            conn.simple_bind_s()
            print(f"✅ Server erreichbar (anonymer Bind)")
            conn.unbind_s()
        except ldap.SERVER_DOWN:
            print(f"❌ Server nicht erreichbar")
        except Exception as e:
            print(f"⚠️  Server erreichbar, aber: {e}")

def print_recommendations():
    """Gibt Empfehlungen zur Fehlerbehebung"""

    print("\n" + "=" * 60)
    print("Empfehlungen zur Fehlerbehebung")
    print("=" * 60)

    print("""
1. LDAP-Server starten (falls lokal):
   sudo systemctl start slapd
   # oder
   sudo systemctl start openldap

2. Server-Erreichbarkeit prüfen:
   telnet ldap.bibelgemeinde-lage.de 636
   # oder
   openssl s_client -connect ldap.bibelgemeinde-lage.de:636

3. Für Entwicklung: SSL-Validierung deaktivieren
   In main/settings.py nach AUTH_LDAP_SERVER_URI hinzufügen:

   import ldap
   ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

4. Auf unverschlüsselten LDAP wechseln (nur Entwicklung!):
   AUTH_LDAP_SERVER_URI = 'ldap://ldap.bibelgemeinde-lage.de:389'

5. Lokalen LDAP-Server verwenden:
   Installiere OpenLDAP lokal und ändere:
   AUTH_LDAP_SERVER_URI = 'ldap://localhost:389'
""")

if __name__ == '__main__':
    success = test_ldap_connection()

    if not success:
        test_alternative_servers()
        print_recommendations()
        sys.exit(1)
    else:
        print("\n✅ Alle Tests erfolgreich!")
        sys.exit(0)
