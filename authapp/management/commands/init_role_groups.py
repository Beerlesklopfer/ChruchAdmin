from django.core.management.base import BaseCommand
from django.conf import settings
from main.ldap_manager import LDAPManager


class Command(BaseCommand):
    help = 'Initialisiert die erforderlichen Rollen-Gruppen im LDAP'

    def handle(self, *args, **options):
        role_groups = [
            ('Pastor', 'Leitende Pastoren der Gemeinde'),
            ('Älteste', 'Mitglieder des Ältestenrates'),
            ('Diakone', 'Diakonale Dienste'),
            ('Sekretariat', 'Verwaltung und Sekretariatsaufgaben'),
        ]

        with LDAPManager() as ldap:
            # Zuerst alle vorhandenen Gruppen auflisten
            existing_groups = []
            all_groups = ldap.list_groups()
            for group in all_groups:
                cn = group['attributes'].get('cn', [''])[0]
                if isinstance(cn, bytes):
                    cn = cn.decode('utf-8')
                existing_groups.append(cn)

            self.stdout.write(f'Vorhandene Gruppen: {", ".join(existing_groups)}')

            for group_name, description in role_groups:
                if group_name in existing_groups:
                    self.stdout.write(
                        self.style.SUCCESS(f'Gruppe "{group_name}" existiert bereits')
                    )
                else:
                    try:
                        # Gruppe erstellen
                        ldap.create_group(group_name, description=description)
                        self.stdout.write(
                            self.style.SUCCESS(f'Gruppe "{group_name}" wurde erstellt')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Fehler beim Erstellen der Gruppe "{group_name}": {e}')
                        )

        self.stdout.write(
            self.style.SUCCESS('Rollen-Gruppen-Initialisierung abgeschlossen')
        )