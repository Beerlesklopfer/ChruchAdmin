from django.core.management.base import BaseCommand
from django.conf import settings
from authapp.models import LDAPConfig
import json


class Command(BaseCommand):
    help = 'Importiert die LDAP-Konfiguration aus settings.py in die Datenbank'

    def handle(self, *args, **options):
        # Prüfe ob bereits eine Konfiguration existiert
        if LDAPConfig.objects.filter(name='Beispielgemeinde LDAP').exists():
            self.stdout.write(
                self.style.WARNING('LDAP-Konfiguration existiert bereits. Überspringe Import.')
            )
            return

        # Hole LDAP-Einstellungen aus settings.py
        server_uri = getattr(settings, 'AUTH_LDAP_SERVER_URI', '')
        bind_dn = getattr(settings, 'AUTH_LDAP_BIND_DN', '')
        bind_password = getattr(settings, 'AUTH_LDAP_BIND_PASSWORD', '')

        # Hole USER_SEARCH
        user_search = getattr(settings, 'AUTH_LDAP_USER_SEARCH', None)
        if user_search:
            user_search_base = user_search.base_dn
            user_search_filter = user_search.filterstr
        else:
            user_search_base = "ou=Users,dc=example-church,dc=de"
            user_search_filter = "(|(cn=%(user)s)(mail=%(user)s))"

        # Hole GROUP_SEARCH
        group_search = getattr(settings, 'AUTH_LDAP_GROUP_SEARCH', None)
        if group_search:
            group_search_base = group_search.base_dn
        else:
            group_search_base = "ou=Groups,dc=example-church,dc=de"

        # Hole Attribute Mapping
        user_attr_map = getattr(settings, 'AUTH_LDAP_USER_ATTR_MAP', {})
        attribute_mapping = json.dumps(user_attr_map, ensure_ascii=False, indent=2)

        # Erstelle LDAPConfig
        config = LDAPConfig.objects.create(
            name='Beispielgemeinde LDAP',
            server_uri=server_uri,
            bind_dn=bind_dn,
            bind_password=bind_password,
            user_search_base=user_search_base,
            user_search_filter=user_search_filter,
            group_search_base=group_search_base,
            attribute_mapping=attribute_mapping,
            is_active=True
        )

        self.stdout.write(
            self.style.SUCCESS(f'✓ LDAP-Konfiguration "{config.name}" erfolgreich importiert!')
        )
        self.stdout.write(f'  Server: {config.server_uri}')
        self.stdout.write(f'  User Search Base: {config.user_search_base}')
        self.stdout.write(f'  Group Search Base: {config.group_search_base}')
