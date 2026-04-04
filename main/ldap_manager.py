"""
LDAP Connection Manager für Church Administration System
Zentrale Klasse für alle LDAP-Operationen mit Error Handling und Logging
"""

import ldap
import ldap.modlist as modlist
from django.conf import settings
from django.utils import timezone
import hashlib
import base64
import os
import logging
import threading

logger = logging.getLogger(__name__)

# Thread-lokaler Cache fuer LDAP-Verbindungen
_thread_local = threading.local()


# Custom Exceptions
class LDAPConnectionError(Exception):
    """LDAP Verbindungsfehler"""
    pass


class LDAPOperationError(Exception):
    """LDAP Operation fehlgeschlagen"""
    pass


class LDAPValidationError(Exception):
    """LDAP Validierungsfehler"""
    pass


class LDAPHierarchyError(Exception):
    """LDAP Hierarchie-Fehler (z.B. Kinder vorhanden beim Löschen)"""
    pass


class LDAPManager:
    """
    Zentrale Klasse für alle LDAP-Operationen
    Unterstützt Context Manager für automatisches Connection Management
    """

    def __init__(self, config_name=None):
        """
        Initialisierung mit Einstellungen aus Datenbank oder settings.py

        Args:
            config_name: Name der LDAPConfig aus der Datenbank (optional)
                        Falls None, wird die erste aktive Konfiguration verwendet
        """
        # Lade Konfiguration aus Datenbank
        ldap_config = self._load_config(config_name)

        if ldap_config:
            # Verwende Datenbank-Konfiguration
            self.server_uri = ldap_config.server_uri
            self.bind_dn = ldap_config.bind_dn
            self.bind_password = ldap_config.bind_password
            self.user_search_base = ldap_config.user_search_base
            self.user_search_filter = ldap_config.user_search_filter
            self.group_search_base = ldap_config.group_search_base
            self.config_source = f"Datenbank ({ldap_config.name})"
            logger.info(f"LDAP-Konfiguration aus Datenbank geladen: {ldap_config.name}")
        else:
            # Fallback zu settings.py
            self.server_uri = settings.AUTH_LDAP_SERVER_URI
            self.bind_dn = settings.AUTH_LDAP_BIND_DN
            self.bind_password = settings.AUTH_LDAP_BIND_PASSWORD
            self.user_search_base = "ou=Users,dc=example-church,dc=de"
            self.user_search_filter = "(|(cn=%(user)s)(mail=%(user)s))"
            self.group_search_base = "ou=Groups,dc=example-church,dc=de"
            self.config_source = "settings.py (Fallback)"
            logger.warning("Keine aktive LDAP-Konfiguration in Datenbank gefunden - verwende settings.py")

        self.base_dn = "dc=example-church,dc=de"
        self.conn = None

    def _load_config(self, config_name=None):
        """
        Lade LDAP-Konfiguration aus Datenbank

        Args:
            config_name: Optional - Name der spezifischen Konfiguration

        Returns:
            LDAPConfig object oder None
        """
        try:
            from authapp.models import LDAPConfig

            if config_name:
                return LDAPConfig.objects.filter(name=config_name, is_active=True).first()
            else:
                # Verwende die erste aktive Konfiguration
                return LDAPConfig.objects.filter(is_active=True).first()
        except Exception as e:
            logger.error(f"Fehler beim Laden der LDAP-Konfiguration: {e}")
            return None

    def __enter__(self):
        """Context Manager: Verbindung herstellen oder aus Cache wiederverwenden"""
        cached = getattr(_thread_local, 'ldap_conn', None)
        if cached and cached.get('conn'):
            try:
                # Prüfe ob Verbindung noch lebt
                cached['conn'].whoami_s()
                self.conn = cached['conn']
                self._is_cached = True
                return self
            except Exception:
                # Verbindung tot — neu aufbauen
                pass
        self._is_cached = False
        self.connect()
        _thread_local.ldap_conn = {'conn': self.conn}
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager: Verbindung im Cache lassen (nicht schliessen)"""
        if not self._is_cached:
            # Verbindung bleibt im Cache fuer den naechsten with-Block
            pass
        return False

    def connect(self):
        """Stelle LDAP-Verbindung her"""
        try:
            logger.info(f"Verbinde mit LDAP Server: {self.server_uri}")
            self.conn = ldap.initialize(self.server_uri)
            self.conn.set_option(ldap.OPT_REFERRALS, 0)
            self.conn.set_option(ldap.OPT_NETWORK_TIMEOUT, 10)
            # SSL-Zertifikat-Validierung deaktivieren (nur für Entwicklung!)
            self.conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
            self.conn.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            self.conn.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
            self.conn.simple_bind_s(self.bind_dn, self.bind_password)
            logger.info("LDAP Verbindung erfolgreich")
        except ldap.INVALID_CREDENTIALS:
            logger.error("LDAP: Ungültige Anmeldedaten")
            raise LDAPConnectionError("Ungültige LDAP-Anmeldedaten")
        except ldap.SERVER_DOWN:
            logger.error("LDAP: Server nicht erreichbar")
            raise LDAPConnectionError("LDAP-Server nicht erreichbar")
        except ldap.LDAPError as e:
            logger.error(f"LDAP Verbindungsfehler: {e}")
            raise LDAPConnectionError(f"LDAP-Verbindungsfehler: {str(e)}")

    def disconnect(self):
        """Schließe LDAP-Verbindung"""
        if self.conn:
            try:
                self.conn.unbind_s()
                logger.info("LDAP Verbindung geschlossen")
            except ldap.LDAPError as e:
                logger.error(f"Fehler beim Schließen der Verbindung: {e}")
            finally:
                self.conn = None

    # ==================== UTILITY METHODS ====================

    def build_dn(self, cn, parent_dn=None, ou="Users"):
        """
        Konstruiere DN (Distinguished Name)

        Args:
            cn: Common Name (Benutzername oder Gruppenname)
            parent_dn: Optional - Parent DN für verschachtelte Einträge
            ou: Organizational Unit (default: Users)

        Returns:
            str: Vollständiger DN

        Beispiele:
            build_dn("Jakob.Derzapf")
            -> "cn=Jakob.Derzapf,ou=Users,dc=example-church,dc=de"

            build_dn("Levi.Derzapf", "cn=Jakob.Derzapf,ou=Users,dc=example-church,dc=de")
            -> "cn=Levi.Derzapf,cn=Jakob.Derzapf,ou=Users,dc=example-church,dc=de"
        """
        if parent_dn:
            # Verschachtelter Eintrag
            return f"cn={cn},{parent_dn}"
        else:
            # Root-Eintrag
            return f"cn={cn},ou={ou},{self.base_dn}"

    def validate_dn(self, dn):
        """
        Validiere DN-Format

        Args:
            dn: Distinguished Name

        Returns:
            bool: True wenn valid

        Raises:
            LDAPValidationError: Bei ungültigem DN
        """
        if not dn or not isinstance(dn, str):
            raise LDAPValidationError("DN darf nicht leer sein")

        if not dn.endswith(self.base_dn):
            raise LDAPValidationError(f"DN muss mit {self.base_dn} enden")

        # Prüfe auf LDAP Injection
        dangerous_chars = [';', '&', '|', '(', ')']
        for char in dangerous_chars:
            if char in dn:
                raise LDAPValidationError(f"Ungültiges Zeichen in DN: {char}")

        return True

    def encode_password(self, password):
        """
        Kodiere Passwort mit SSHA (Salted SHA-1)

        Args:
            password: Klartext-Passwort

        Returns:
            str: {SSHA}base64(sha1(password+salt)+salt)
        """
        salt = os.urandom(4)
        sha = hashlib.sha1(password.encode('utf-8'))
        sha.update(salt)
        digest = sha.digest()
        ssha = base64.b64encode(digest + salt).decode('ascii')
        return f"{{SSHA}}{ssha}"

    def decode_attribute(self, value):
        """
        Dekodiere LDAP-Attribut (bytes zu str)

        Args:
            value: bytes oder list of bytes

        Returns:
            str oder list of str
        """
        if isinstance(value, bytes):
            return value.decode('utf-8')
        elif isinstance(value, list):
            return [v.decode('utf-8') if isinstance(v, bytes) else v for v in value]
        return value

    def encode_attribute(self, value):
        """
        Kodiere Attribut für LDAP (str zu bytes)

        Args:
            value: str oder list of str

        Returns:
            bytes oder list of bytes
        """
        if isinstance(value, str):
            return value.encode('utf-8')
        elif isinstance(value, list):
            return [v.encode('utf-8') if isinstance(v, str) else v for v in value]
        return value

    # ==================== USER OPERATIONS ====================

    def get_user(self, cn, parent_cn=None):
        """
        Hole einen Benutzer aus dem LDAP

        Args:
            cn: Common Name des Benutzers
            parent_cn: Optional - Parent CN bei verschachtelten Benutzern

        Returns:
            dict: {'dn': str, 'attributes': dict} oder None
        """
        try:
            if parent_cn:
                search_base = self.build_dn(parent_cn)
                search_scope = ldap.SCOPE_ONELEVEL
            else:
                search_base = f"ou=Users,{self.base_dn}"
                search_scope = ldap.SCOPE_SUBTREE

            # Case-insensitive Suche per cn-Filter
            result = self.conn.search_s(
                search_base,
                search_scope,
                f"(cn={cn})",
                None
            )

            if result:
                dn, attrs = result[0]
                # Dekodiere alle Attribute (ausser binaere)
                BINARY_ATTRS = {'jpegPhoto', 'userCertificate', 'objectSid'}
                decoded_attrs = {}
                for key, value in attrs.items():
                    if key in BINARY_ATTRS:
                        decoded_attrs[key] = value  # Binaer belassen
                    else:
                        decoded_attrs[key] = self.decode_attribute(value)

                logger.info(f"Benutzer gefunden: {cn}")
                return {'dn': dn, 'attributes': decoded_attrs}

            return None

        except ldap.NO_SUCH_OBJECT:
            logger.warning(f"Benutzer nicht gefunden: {cn}")
            return None
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Abrufen von Benutzer {cn}: {e}")
            raise LDAPOperationError(f"Fehler beim Abrufen: {str(e)}")

    def list_users(self, parent_dn=None, filter_str="(objectClass=inetOrgPerson)"):
        """
        Liste alle Benutzer auf

        Args:
            parent_dn: Optional - Nur Benutzer unter diesem Parent
            filter_str: LDAP Filter

        Returns:
            list: Liste von {'dn': str, 'attributes': dict}
        """
        try:
            if parent_dn:
                search_base = parent_dn
                search_scope = ldap.SCOPE_ONELEVEL
            else:
                search_base = f"ou=Users,{self.base_dn}"
                search_scope = ldap.SCOPE_SUBTREE

            results = self.conn.search_s(
                search_base,
                search_scope,
                filter_str,
                None
            )

            BINARY_ATTRS = {'jpegPhoto', 'userCertificate', 'objectSid'}
            users = []
            for dn, attrs in results:
                if dn:
                    decoded_attrs = {}
                    for key, value in attrs.items():
                        if key in BINARY_ATTRS:
                            decoded_attrs[key] = value
                        else:
                            decoded_attrs[key] = self.decode_attribute(value)
                    users.append({'dn': dn, 'attributes': decoded_attrs})

            logger.info(f"Gefundene Benutzer: {len(users)}")
            return users

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Auflisten der Benutzer: {e}")
            raise LDAPOperationError(f"Fehler beim Auflisten: {str(e)}")

    def _next_uid_number(self):
        """Ermittelt die naechste freie uidNumber aus dem LDAP"""
        try:
            results = self.conn.search_s(
                self.user_search_base,
                ldap.SCOPE_SUBTREE,
                "(objectClass=posixAccount)",
                ['uidNumber']
            )
            max_uid = 10000  # Startwert
            for dn, attrs in results:
                uid_vals = attrs.get('uidNumber', [])
                for uid_val in uid_vals:
                    if isinstance(uid_val, bytes):
                        uid_val = uid_val.decode('utf-8')
                    try:
                        uid_int = int(uid_val)
                        if uid_int > max_uid:
                            max_uid = uid_int
                    except ValueError:
                        pass
            return max_uid + 1
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Ermitteln der naechsten uidNumber: {e}")
            return 10000

    def create_user(self, attributes, parent_cn=None):
        """
        Erstelle neuen LDAP-Benutzer

        Args:
            attributes: dict mit Benutzerattributen (cn, sn, givenName, mail, etc.)
            parent_cn: Optional - Parent CN für verschachtelte Benutzer

        Returns:
            str: DN des erstellten Benutzers

        Required attributes:
            - cn, uid, sn, givenName, mail, userPassword
            - uidNumber, gidNumber, homeDirectory, loginShell
        """
        try:
            cn = attributes.get('cn')
            if not cn:
                raise LDAPValidationError("cn ist erforderlich")

            if parent_cn:
                user_dn = self.build_dn(cn, self.build_dn(parent_cn))
            else:
                user_dn = self.build_dn(cn)

            self.validate_dn(user_dn)

            # Setze ObjectClasses
            if 'objectClass' not in attributes:
                attributes['objectClass'] = [
                    b'top',
                    b'person',
                    b'organizationalPerson',
                    b'inetOrgPerson',
                    b'posixAccount',
                    b'postModernalPerson',
                ]

            # Automatische POSIX-Attribute vergeben
            if 'uidNumber' not in attributes:
                attributes['uidNumber'] = str(self._next_uid_number())
            if 'gidNumber' not in attributes:
                attributes['gidNumber'] = '30000'
            if 'uid' not in attributes:
                attributes['uid'] = cn
            if 'homeDirectory' not in attributes:
                attributes['homeDirectory'] = f'/home/example-church.de/{cn}'
            if 'loginShell' not in attributes:
                attributes['loginShell'] = '/bin/false'

            # Enkodiere alle Attribute
            encoded_attrs = {}
            for key, value in attributes.items():
                if key == 'objectClass' and isinstance(value, list):
                    # objectClass bleibt als Liste
                    encoded_attrs[key] = value
                else:
                    encoded_attrs[key] = self.encode_attribute(value) if not isinstance(value, bytes) else value

            ldif = modlist.addModlist(encoded_attrs)
            self.conn.add_s(user_dn, ldif)

            logger.info(f"Benutzer erstellt: {user_dn}")
            return user_dn

        except ldap.ALREADY_EXISTS:
            logger.error(f"Benutzer existiert bereits: {cn}")
            raise LDAPOperationError(f"Benutzer {cn} existiert bereits")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Erstellen von Benutzer {cn}: {e}")
            raise LDAPOperationError(f"Fehler beim Erstellen: {str(e)}")

    def update_user(self, cn, attributes, parent_cn=None):
        """
        Aktualisiere Benutzer-Attribute

        Args:
            cn: Common Name des Benutzers
            attributes: dict mit zu ändernden Attributen
            parent_cn: Optional - Parent CN bei verschachtelten Benutzern

        Returns:
            bool: True bei Erfolg
        """
        try:
            if parent_cn:
                user_dn = self.build_dn(cn, self.build_dn(parent_cn))
            else:
                user_dn = self.build_dn(cn)

            self.validate_dn(user_dn)

            # Hole alte Attribute
            old_user = self.get_user(cn, parent_cn)
            if not old_user:
                raise LDAPOperationError(f"Benutzer {cn} nicht gefunden")

            old_attrs = old_user['attributes']

            # Erstelle Modlist
            mod_attrs = []
            for key, value in attributes.items():
                encoded_value = self.encode_attribute(value)
                if key in old_attrs:
                    # Ersetze bestehendes Attribut
                    mod_attrs.append((ldap.MOD_REPLACE, key, encoded_value))
                else:
                    # Füge neues Attribut hinzu
                    mod_attrs.append((ldap.MOD_ADD, key, encoded_value))

            if mod_attrs:
                self.conn.modify_s(user_dn, mod_attrs)
                logger.info(f"Benutzer aktualisiert: {user_dn}")
                return True

            return False

        except ldap.NO_SUCH_OBJECT:
            logger.error(f"Benutzer nicht gefunden: {cn}")
            raise LDAPOperationError(f"Benutzer {cn} nicht gefunden")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Aktualisieren von Benutzer {cn}: {e}")
            raise LDAPOperationError(f"Fehler beim Aktualisieren: {str(e)}")

    def move_user(self, cn, old_parent_cn=None, new_parent_cn=None):
        """
        Verschiebt einen User zu einem neuen Elternteil oder auf Top-Level.

        Args:
            cn: Common Name des Users
            old_parent_cn: Aktueller Elternteil (None = Top-Level)
            new_parent_cn: Neuer Elternteil (None = Top-Level)

        Returns:
            str: Neuer DN
        """
        try:
            # Alten DN bauen
            if old_parent_cn:
                old_dn = self.build_dn(cn, self.build_dn(old_parent_cn))
            else:
                old_dn = self.build_dn(cn)

            # Neuen Superior bauen
            if new_parent_cn:
                new_superior = self.build_dn(new_parent_cn)
            else:
                new_superior = f"ou=Users,{self.base_dn}"

            new_rdn = f"cn={cn}"

            self.conn.rename_s(old_dn, new_rdn, new_superior)

            new_dn = f"{new_rdn},{new_superior}"
            logger.info(f"User verschoben: {old_dn} -> {new_dn}")
            return new_dn

        except ldap.NO_SUCH_OBJECT:
            raise LDAPOperationError(f"User {cn} nicht gefunden")
        except ldap.ALREADY_EXISTS:
            raise LDAPOperationError(f"User {cn} existiert bereits unter dem Ziel")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Verschieben von {cn}: {e}")
            raise LDAPOperationError(f"Fehler beim Verschieben: {str(e)}")

    def delete_user(self, cn, parent_cn=None, force=False):
        """
        Lösche Benutzer aus LDAP

        Args:
            cn: Common Name des Benutzers
            parent_cn: Optional - Parent CN bei verschachtelten Benutzern
            force: Bei True werden auch Kinder gelöscht

        Returns:
            bool: True bei Erfolg
        """
        try:
            if parent_cn:
                user_dn = self.build_dn(cn, self.build_dn(parent_cn))
            else:
                user_dn = self.build_dn(cn)

            self.validate_dn(user_dn)

            # Prüfe auf Kinder
            children = self.list_users(parent_dn=user_dn)
            if children and not force:
                raise LDAPHierarchyError(
                    f"Benutzer {cn} hat {len(children)} Kind(er). "
                    "Verwende force=True zum Löschen mit Kindern."
                )

            # Lösche zuerst alle Kinder (rekursiv)
            if force and children:
                for child in children:
                    child_cn = child['attributes']['cn'][0] if isinstance(child['attributes']['cn'], list) else child['attributes']['cn']
                    self.delete_user(child_cn, parent_cn=cn, force=True)

            # Lösche Benutzer
            self.conn.delete_s(user_dn)
            logger.info(f"Benutzer gelöscht: {user_dn}")
            return True

        except ldap.NO_SUCH_OBJECT:
            logger.error(f"Benutzer nicht gefunden: {cn}")
            raise LDAPOperationError(f"Benutzer {cn} nicht gefunden")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Löschen von Benutzer {cn}: {e}")
            raise LDAPOperationError(f"Fehler beim Löschen: {str(e)}")

    def get_user_tree(self, parent_cn):
        """
        Hole Familien-Hierarchie als Baum

        Args:
            parent_cn: Common Name des Elternteils

        Returns:
            dict: {'user': dict, 'children': list}
        """
        try:
            parent_user = self.get_user(parent_cn)
            if not parent_user:
                return None

            children_list = self.list_users(parent_dn=parent_user['dn'])

            tree = {
                'user': parent_user,
                'children': []
            }

            for child in children_list:
                child_cn = child['attributes']['cn'][0] if isinstance(child['attributes']['cn'], list) else child['attributes']['cn']
                # Rekursiv Kinder holen
                child_tree = self.get_user_tree(child_cn)
                if child_tree:
                    tree['children'].append(child_tree)

            return tree

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Benutzer-Baums: {e}")
            raise LDAPOperationError(f"Fehler beim Erstellen des Baums: {str(e)}")

    # ==================== GROUP OPERATIONS ====================

    def get_group(self, group_dn):
        """
        Hole Gruppe aus LDAP

        Args:
            group_dn: Distinguished Name der Gruppe

        Returns:
            dict: {'dn': str, 'attributes': dict} oder None
        """
        try:
            self.validate_dn(group_dn)

            result = self.conn.search_s(
                group_dn,
                ldap.SCOPE_BASE,
                "(objectClass=*)",
                None
            )

            if result:
                dn, attrs = result[0]
                decoded_attrs = {}
                for key, value in attrs.items():
                    decoded_attrs[key] = self.decode_attribute(value)

                logger.info(f"Gruppe gefunden: {group_dn}")
                return {'dn': dn, 'attributes': decoded_attrs}

            return None

        except ldap.NO_SUCH_OBJECT:
            logger.warning(f"Gruppe nicht gefunden: {group_dn}")
            return None
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Abrufen der Gruppe: {e}")
            raise LDAPOperationError(f"Fehler beim Abrufen: {str(e)}")

    def list_groups(self, parent_dn=None, filter_str="(objectClass=groupOfNames)"):
        """
        Liste alle Gruppen auf

        Args:
            parent_dn: Optional - Nur Gruppen unter diesem Parent
            filter_str: LDAP Filter

        Returns:
            list: Liste von {'dn': str, 'attributes': dict}
        """
        try:
            if parent_dn:
                search_base = parent_dn
                search_scope = ldap.SCOPE_ONELEVEL
            else:
                search_base = f"ou=Groups,{self.base_dn}"
                search_scope = ldap.SCOPE_SUBTREE

            results = self.conn.search_s(
                search_base,
                search_scope,
                filter_str,
                None
            )

            groups = []
            for dn, attrs in results:
                if dn:
                    decoded_attrs = {}
                    for key, value in attrs.items():
                        decoded_attrs[key] = self.decode_attribute(value)
                    groups.append({'dn': dn, 'attributes': decoded_attrs})

            logger.info(f"Gefundene Gruppen: {len(groups)}")
            return groups

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Auflisten der Gruppen: {e}")
            raise LDAPOperationError(f"Fehler beim Auflisten: {str(e)}")

    def create_group(self, name, parent_dn=None, mail_enabled=False, description=""):
        """
        Erstelle neue LDAP-Gruppe

        Args:
            name: Gruppenname
            parent_dn: Optional - Parent DN für hierarchische Gruppen
            mail_enabled: Bool - Mail-Routing aktivieren
            description: Beschreibung der Gruppe

        Returns:
            str: DN der erstellten Gruppe
        """
        try:
            if parent_dn:
                group_dn = self.build_dn(name, parent_dn, ou="Groups")
            else:
                group_dn = self.build_dn(name, ou="Groups")

            self.validate_dn(group_dn)

            # Basis ObjectClasses
            object_classes = [
                b'top',
                b'groupOfNames',
                b'nextCloudGroup'
            ]

            if mail_enabled:
                object_classes.append(b'groupMail')

            attributes = {
                'objectClass': object_classes,
                'cn': self.encode_attribute(name),
                'member': b'cn=nobody'  # Required by groupOfNames
            }

            if description:
                attributes['description'] = self.encode_attribute(description)

            ldif = modlist.addModlist(attributes)
            self.conn.add_s(group_dn, ldif)

            logger.info(f"Gruppe erstellt: {group_dn}")
            return group_dn

        except ldap.ALREADY_EXISTS:
            logger.error(f"Gruppe existiert bereits: {name}")
            raise LDAPOperationError(f"Gruppe {name} existiert bereits")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Erstellen der Gruppe {name}: {e}")
            raise LDAPOperationError(f"Fehler beim Erstellen: {str(e)}")

    def update_group(self, group_dn, attributes):
        """
        Aktualisiere Gruppen-Attribute

        Args:
            group_dn: Distinguished Name der Gruppe
            attributes: dict mit zu ändernden Attributen

        Returns:
            bool: True bei Erfolg
        """
        try:
            self.validate_dn(group_dn)

            # Hole alte Attribute
            old_group = self.get_group(group_dn)
            if not old_group:
                raise LDAPOperationError(f"Gruppe nicht gefunden: {group_dn}")

            old_attrs = old_group['attributes']

            # Erstelle Modlist
            mod_attrs = []
            for key, value in attributes.items():
                encoded_value = self.encode_attribute(value)
                if key in old_attrs:
                    mod_attrs.append((ldap.MOD_REPLACE, key, encoded_value))
                else:
                    mod_attrs.append((ldap.MOD_ADD, key, encoded_value))

            if mod_attrs:
                self.conn.modify_s(group_dn, mod_attrs)
                logger.info(f"Gruppe aktualisiert: {group_dn}")
                return True

            return False

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Aktualisieren der Gruppe: {e}")
            raise LDAPOperationError(f"Fehler beim Aktualisieren: {str(e)}")

    def delete_group(self, group_dn, force=False):
        """
        Lösche Gruppe aus LDAP

        Args:
            group_dn: Distinguished Name der Gruppe
            force: Bei True werden auch Untergruppen gelöscht

        Returns:
            bool: True bei Erfolg
        """
        try:
            self.validate_dn(group_dn)

            # Prüfe auf Untergruppen
            subgroups = self.list_groups(parent_dn=group_dn)
            if subgroups and not force:
                raise LDAPHierarchyError(
                    f"Gruppe hat {len(subgroups)} Untergruppe(n). "
                    "Verwende force=True zum Löschen mit Untergruppen."
                )

            # Lösche zuerst alle Untergruppen (rekursiv)
            if force and subgroups:
                for subgroup in subgroups:
                    self.delete_group(subgroup['dn'], force=True)

            # Lösche Gruppe
            self.conn.delete_s(group_dn)
            logger.info(f"Gruppe gelöscht: {group_dn}")
            return True

        except ldap.NO_SUCH_OBJECT:
            logger.error(f"Gruppe nicht gefunden: {group_dn}")
            raise LDAPOperationError(f"Gruppe nicht gefunden")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Löschen der Gruppe: {e}")
            raise LDAPOperationError(f"Fehler beim Löschen: {str(e)}")

    def add_member(self, group_dn, user_dn):
        """
        Füge Mitglied zu Gruppe hinzu

        Args:
            group_dn: Distinguished Name der Gruppe
            user_dn: Distinguished Name des Benutzers

        Returns:
            bool: True bei Erfolg
        """
        try:
            self.validate_dn(group_dn)
            self.validate_dn(user_dn)

            mod_attrs = [
                (ldap.MOD_ADD, 'member', self.encode_attribute(user_dn))
            ]

            self.conn.modify_s(group_dn, mod_attrs)
            logger.info(f"Mitglied hinzugefügt: {user_dn} zu {group_dn}")
            return True

        except ldap.TYPE_OR_VALUE_EXISTS:
            logger.warning(f"Mitglied bereits in Gruppe: {user_dn}")
            return False
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Hinzufügen des Mitglieds: {e}")
            raise LDAPOperationError(f"Fehler beim Hinzufügen: {str(e)}")

    def remove_member(self, group_dn, user_dn):
        """
        Entferne Mitglied aus Gruppe

        Args:
            group_dn: Distinguished Name der Gruppe
            user_dn: Distinguished Name des Benutzers

        Returns:
            bool: True bei Erfolg
        """
        try:
            self.validate_dn(group_dn)
            self.validate_dn(user_dn)

            mod_attrs = [
                (ldap.MOD_DELETE, 'member', self.encode_attribute(user_dn))
            ]

            self.conn.modify_s(group_dn, mod_attrs)
            logger.info(f"Mitglied entfernt: {user_dn} aus {group_dn}")
            return True

        except ldap.NO_SUCH_ATTRIBUTE:
            logger.warning(f"Mitglied nicht in Gruppe: {user_dn}")
            return False
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Entfernen des Mitglieds: {e}")
            raise LDAPOperationError(f"Fehler beim Entfernen: {str(e)}")

    def get_group_tree(self, parent_dn=None):
        """
        Hole Gruppenhierarchie als Baum

        Args:
            parent_dn: Optional - Parent DN (sonst Root-Gruppen)

        Returns:
            list: Liste von {'group': dict, 'children': list}
        """
        try:
            if parent_dn is None:
                parent_dn = f"ou=Groups,{self.base_dn}"

            groups = self.list_groups(parent_dn=parent_dn)

            tree = []
            for group in groups:
                # Hole Untergruppen rekursiv
                subgroups = self.get_group_tree(parent_dn=group['dn'])
                tree.append({
                    'group': group,
                    'children': subgroups
                })

            return tree

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Gruppen-Baums: {e}")
            raise LDAPOperationError(f"Fehler beim Erstellen des Baums: {str(e)}")

    # ==================== MAIL OPERATIONS ====================

    def configure_user_mail(self, user_dn, routing_addresses=None, aliases=None, quota="500M", enabled=True):
        """
        Konfiguriere Mail für Benutzer

        Args:
            user_dn: Distinguished Name des Benutzers
            routing_addresses: list - Mail-Weiterleitungsadressen
            aliases: list - Mail-Aliases
            quota: str - Mail-Quota (z.B. "500M")
            enabled: bool - Mail-Routing aktiviert

        Returns:
            bool: True bei Erfolg
        """
        try:
            self.validate_dn(user_dn)

            mod_attrs = []

            # Füge mailExtension ObjectClass hinzu (falls noch nicht vorhanden)
            user = self.get_user(user_dn.split(',')[0].split('=')[1])
            if user and b'mailExtension' not in user['attributes'].get('objectClass', []):
                mod_attrs.append((ldap.MOD_ADD, 'objectClass', b'mailExtension'))

            if routing_addresses:
                encoded_addrs = [self.encode_attribute(addr) for addr in routing_addresses]
                mod_attrs.append((ldap.MOD_REPLACE, 'mailRoutingAddress', encoded_addrs))

            if aliases:
                encoded_aliases = [self.encode_attribute(alias) for alias in aliases]
                mod_attrs.append((ldap.MOD_REPLACE, 'mailAliasAddress', encoded_aliases))

            mod_attrs.append((ldap.MOD_REPLACE, 'mailQuota', self.encode_attribute(quota)))
            mod_attrs.append((ldap.MOD_REPLACE, 'mailRoutingEnabled', b'TRUE' if enabled else b'FALSE'))

            if mod_attrs:
                self.conn.modify_s(user_dn, mod_attrs)
                logger.info(f"Mail konfiguriert für: {user_dn}")
                return True

            return False

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Konfigurieren der Mail: {e}")
            raise LDAPOperationError(f"Fehler bei Mail-Konfiguration: {str(e)}")

    def configure_group_mail(self, group_dn, routing_address, enabled=True):
        """
        Konfiguriere Mail für Gruppe

        Args:
            group_dn: Distinguished Name der Gruppe
            routing_address: str - Mail-Adresse der Gruppe
            enabled: bool - Mail-Routing aktiviert

        Returns:
            bool: True bei Erfolg
        """
        try:
            self.validate_dn(group_dn)

            mod_attrs = [
                (ldap.MOD_REPLACE, 'mailRoutingAddress', self.encode_attribute(routing_address)),
                (ldap.MOD_REPLACE, 'mailRoutingEnabled', b'TRUE' if enabled else b'FALSE')
            ]

            # Füge groupMail ObjectClass hinzu (falls noch nicht vorhanden)
            group = self.get_group(group_dn)
            if group and b'groupMail' not in group['attributes'].get('objectClass', []):
                mod_attrs.append((ldap.MOD_ADD, 'objectClass', b'groupMail'))

            self.conn.modify_s(group_dn, mod_attrs)
            logger.info(f"Mail konfiguriert für Gruppe: {group_dn}")
            return True

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Konfigurieren der Gruppen-Mail: {e}")
            raise LDAPOperationError(f"Fehler bei Mail-Konfiguration: {str(e)}")

    def list_mail_domains(self):
        """
        Liste alle Mail-Domains auf

        Returns:
            list: Liste von {'dn': str, 'attributes': dict}
        """
        try:
            search_base = f"ou=Domains,{self.base_dn}"
            results = self.conn.search_s(
                search_base,
                ldap.SCOPE_ONELEVEL,
                "(objectClass=mailDomain)",
                None
            )

            domains = []
            for dn, attrs in results:
                if dn:
                    decoded_attrs = {}
                    for key, value in attrs.items():
                        decoded_attrs[key] = self.decode_attribute(value)
                    domains.append({'dn': dn, 'attributes': decoded_attrs})

            logger.info(f"Gefundene Mail-Domains: {len(domains)}")
            return domains

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Auflisten der Domains: {e}")
            raise LDAPOperationError(f"Fehler beim Auflisten: {str(e)}")

    def create_mail_domain(self, domain_name):
        """
        Erstelle neue Mail-Domain

        Args:
            domain_name: str - Domain-Name (z.B. "example.de")

        Returns:
            str: DN der erstellten Domain
        """
        try:
            domain_dn = f"dc={domain_name},ou=Domains,{self.base_dn}"
            self.validate_dn(domain_dn)

            attributes = {
                'objectClass': [b'top', b'dNSDomain', b'mailDomain'],
                'dc': self.encode_attribute(domain_name),
                'mailDomainName': self.encode_attribute(domain_name)
            }

            ldif = modlist.addModlist(attributes)
            self.conn.add_s(domain_dn, ldif)

            logger.info(f"Mail-Domain erstellt: {domain_dn}")
            return domain_dn

        except ldap.ALREADY_EXISTS:
            logger.error(f"Domain existiert bereits: {domain_name}")
            raise LDAPOperationError(f"Domain {domain_name} existiert bereits")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Erstellen der Domain: {e}")
            raise LDAPOperationError(f"Fehler beim Erstellen: {str(e)}")

    def delete_mail_domain(self, domain_name):
        """
        Lösche Mail-Domain

        Args:
            domain_name: str - Domain-Name

        Returns:
            bool: True bei Erfolg
        """
        try:
            domain_dn = f"dc={domain_name},ou=Domains,{self.base_dn}"
            self.validate_dn(domain_dn)

            self.conn.delete_s(domain_dn)
            logger.info(f"Mail-Domain gelöscht: {domain_dn}")
            return True

        except ldap.NO_SUCH_OBJECT:
            logger.error(f"Domain nicht gefunden: {domain_name}")
            raise LDAPOperationError(f"Domain {domain_name} nicht gefunden")
        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Löschen der Domain: {e}")
            raise LDAPOperationError(f"Fehler beim Löschen: {str(e)}")

    def change_password(self, username, new_password):
        """
        Ändert das Passwort eines Benutzers im LDAP

        Args:
            username (str): Benutzername (cn)
            new_password (str): Neues Passwort im Klartext

        Returns:
            bool: True bei Erfolg

        Raises:
            LDAPOperationError: Bei Fehlern
        """
        try:
            # Finde Benutzer
            user = self.get_user(username)
            if not user:
                raise LDAPOperationError(f"Benutzer {username} nicht gefunden")

            user_dn = user['dn']

            # Hash Passwort mit SSHA
            password_hash = self.encode_password(new_password)

            # Setze neues Passwort (muss bytes sein für modify_s)
            if isinstance(password_hash, str):
                password_hash = password_hash.encode('utf-8')
            mod_attrs = [
                (ldap.MOD_REPLACE, 'userPassword', [password_hash])
            ]

            self.conn.modify_s(user_dn, mod_attrs)
            logger.info(f"Passwort geändert für Benutzer: {user_dn}")

            return True

        except ldap.LDAPError as e:
            logger.error(f"Fehler beim Ändern des Passworts: {e}")
            raise LDAPOperationError(f"Fehler beim Passwort-Ändern: {str(e)}")

    def process_photo(self, photo_file):
        """
        Verarbeite Foto für jpegPhoto-Attribut

        Args:
            photo_file: UploadedFile object von Django

        Returns:
            bytes: Foto-Daten als Bytes für LDAP
        """
        try:
            # Lese Foto-Bytes
            photo_bytes = photo_file.read()

            # Validiere Dateigröße (max 1MB)
            max_size = 1 * 1024 * 1024  # 1MB
            if len(photo_bytes) > max_size:
                raise LDAPValidationError("Foto zu groß. Maximum 1MB erlaubt.")

            # Validiere JPEG-Format (einfache Prüfung)
            if not photo_bytes.startswith(b'\xff\xd8'):
                raise LDAPValidationError("Nur JPEG-Bilder werden unterstützt.")

            logger.info(f"Foto verarbeitet: {len(photo_bytes)} Bytes")
            return photo_bytes

        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten des Fotos: {e}")
            raise LDAPValidationError(f"Fehler beim Verarbeiten des Fotos: {str(e)}")

    def get_photo_as_base64(self, cn, parent_cn=None):
        """
        Hole jpegPhoto als Base64-String für HTML-Anzeige

        Args:
            cn: Common Name des Benutzers
            parent_cn: Optional - Parent CN bei verschachtelten Benutzern

        Returns:
            str: Base64-kodiertes Foto oder None
        """
        try:
            user = self.get_user(cn, parent_cn)
            if not user:
                return None

            attributes = user['attributes']
            photo_bytes = attributes.get('jpegPhoto')

            if photo_bytes:
                # jpegPhoto ist bereits als bytes
                if isinstance(photo_bytes, list):
                    photo_bytes = photo_bytes[0]

                # Konvertiere zu Base64
                import base64
                photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
                return photo_base64

            return None

        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Fotos: {e}")
            return None

    # ==================== BACKUP & EXPORT ====================

    def export_to_ldif(self, output_path, backup_type='full', base_dn=None):
        """
        Exportiert LDAP-Daten in LDIF-Format

        Args:
            output_path (str): Pfad zur Ausgabe-LDIF-Datei
            backup_type (str): 'full', 'users', 'groups', 'domains'
            base_dn (str): Optional - spezifische Base DN (überschreibt backup_type)

        Returns:
            dict: Statistiken über den Export
                {
                    'entry_count': int,
                    'user_count': int,
                    'group_count': int,
                    'domain_count': int,
                    'file_size': int,
                    'success': bool,
                    'error': str (optional)
                }
        """
        stats = {
            'entry_count': 0,
            'user_count': 0,
            'group_count': 0,
            'domain_count': 0,
            'file_size': 0,
            'success': False,
            'error': None
        }

        try:
            # Bestimme Search Base
            if base_dn:
                search_base = base_dn
            elif backup_type == 'users':
                search_base = self.user_search_base
            elif backup_type == 'groups':
                search_base = self.group_search_base
            elif backup_type == 'domains':
                search_base = f"ou=Domains,{self.base_dn}"
            else:  # full
                search_base = self.base_dn

            logger.info(f"LDIF-Export gestartet: {backup_type} von {search_base}")

            # LDAP-Suche durchführen
            search_filter = "(objectClass=*)"
            search_scope = ldap.SCOPE_SUBTREE

            # Alle Attribute abrufen
            result = self.conn.search_s(
                search_base,
                search_scope,
                search_filter,
                None  # Alle Attribute
            )

            # LDIF-Datei schreiben
            with open(output_path, 'w', encoding='utf-8') as ldif_file:
                for dn, attributes in result:
                    if dn is None:
                        continue

                    stats['entry_count'] += 1

                    # Zähle Typ
                    object_classes = attributes.get('objectClass', [])
                    if isinstance(object_classes, bytes):
                        object_classes = [object_classes]
                    object_classes_str = [
                        oc.decode('utf-8') if isinstance(oc, bytes) else oc
                        for oc in object_classes
                    ]

                    if 'inetOrgPerson' in object_classes_str or 'posixAccount' in object_classes_str:
                        stats['user_count'] += 1
                    elif 'groupOfNames' in object_classes_str:
                        stats['group_count'] += 1
                    elif 'mailDomain' in object_classes_str:
                        stats['domain_count'] += 1

                    # DN schreiben
                    ldif_file.write(f"dn: {dn}\n")

                    # Attribute schreiben
                    for attr, values in attributes.items():
                        if isinstance(values, bytes):
                            values = [values]

                        for value in values:
                            # Binäre Attribute (z.B. Fotos) als Base64
                            if isinstance(value, bytes):
                                # Prüfe ob es Text ist
                                try:
                                    value_str = value.decode('utf-8')
                                    ldif_file.write(f"{attr}: {value_str}\n")
                                except UnicodeDecodeError:
                                    # Binäre Daten - Base64 kodieren
                                    import base64
                                    value_b64 = base64.b64encode(value).decode('ascii')
                                    ldif_file.write(f"{attr}:: {value_b64}\n")
                            else:
                                ldif_file.write(f"{attr}: {value}\n")

                    # Leere Zeile zwischen Einträgen
                    ldif_file.write("\n")

            # Dateigröße ermitteln
            stats['file_size'] = os.path.getsize(output_path)
            stats['success'] = True

            logger.info(
                f"LDIF-Export erfolgreich: {stats['entry_count']} Einträge, "
                f"{stats['file_size']} Bytes"
            )

        except ldap.NO_SUCH_OBJECT as e:
            error_msg = f"Base DN nicht gefunden: {search_base}"
            logger.error(error_msg)
            stats['error'] = error_msg
            stats['success'] = False

        except ldap.LDAPError as e:
            error_msg = f"LDAP-Fehler beim Export: {str(e)}"
            logger.error(error_msg)
            stats['error'] = error_msg
            stats['success'] = False

        except IOError as e:
            error_msg = f"Fehler beim Schreiben der LDIF-Datei: {str(e)}"
            logger.error(error_msg)
            stats['error'] = error_msg
            stats['success'] = False

        except Exception as e:
            error_msg = f"Unerwarteter Fehler beim LDIF-Export: {str(e)}"
            logger.error(error_msg)
            stats['error'] = error_msg
            stats['success'] = False

        return stats

    def import_from_ldif(self, ldif_path, delete_existing=False):
        """
        Importiert LDAP-Daten aus LDIF-Datei

        Args:
            ldif_path (str): Pfad zur LDIF-Datei
            delete_existing (bool): Wenn True, werden bestehende Einträge gelöscht

        Returns:
            dict: Statistiken über den Import
                {
                    'success': bool,
                    'imported_count': int,
                    'skipped_count': int,
                    'error_count': int,
                    'errors': list
                }
        """
        stats = {
            'success': False,
            'imported_count': 0,
            'skipped_count': 0,
            'error_count': 0,
            'errors': []
        }

        try:
            import ldif
            from io import BytesIO

            logger.info(f"LDIF-Import gestartet: {ldif_path}")

            # LDIF-Datei lesen
            with open(ldif_path, 'rb') as ldif_file:
                parser = ldif.LDIFRecordList(ldif_file)
                parser.parse()

                for dn, attributes in parser.all_records:
                    try:
                        # Prüfe ob Eintrag existiert
                        try:
                            self.conn.search_s(dn, ldap.SCOPE_BASE)
                            entry_exists = True
                        except ldap.NO_SUCH_OBJECT:
                            entry_exists = False

                        if entry_exists:
                            if delete_existing:
                                # Lösche und erstelle neu
                                self.conn.delete_s(dn)
                                self.conn.add_s(dn, ldap.modlist.addModlist(attributes))
                                stats['imported_count'] += 1
                            else:
                                # Überspringe bestehende Einträge
                                stats['skipped_count'] += 1
                        else:
                            # Neuer Eintrag
                            self.conn.add_s(dn, ldap.modlist.addModlist(attributes))
                            stats['imported_count'] += 1

                    except ldap.LDAPError as e:
                        error_msg = f"Fehler beim Importieren von {dn}: {str(e)}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)
                        stats['error_count'] += 1

            stats['success'] = True
            logger.info(
                f"LDIF-Import abgeschlossen: {stats['imported_count']} importiert, "
                f"{stats['skipped_count']} übersprungen, {stats['error_count']} Fehler"
            )

        except FileNotFoundError:
            error_msg = f"LDIF-Datei nicht gefunden: {ldif_path}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)

        except Exception as e:
            error_msg = f"Unerwarteter Fehler beim LDIF-Import: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)

        return stats
