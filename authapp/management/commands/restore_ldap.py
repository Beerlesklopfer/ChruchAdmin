"""
Django Management Command fuer LDAP Restore
Importiert LDAP-Daten aus LDIF-Backup-Dateien
"""

from django.core.management.base import BaseCommand, CommandError
from main.ldap_manager import LDAPManager, LDAPConnectionError


class Command(BaseCommand):
    help = 'Importiert LDAP-Daten aus einer LDIF-Backup-Datei'

    def add_arguments(self, parser):
        parser.add_argument(
            'ldif_file',
            type=str,
            help='Pfad zur LDIF-Backup-Datei'
        )
        parser.add_argument(
            '--delete-existing',
            action='store_true',
            default=False,
            help='Bestehende Eintraege vor dem Import loeschen (GEFAEHRLICH!)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Nur pruefen, keine Aenderungen vornehmen'
        )

    def handle(self, *args, **options):
        ldif_file = options['ldif_file']
        delete_existing = options['delete_existing']
        dry_run = options['dry_run']

        import os
        if not os.path.exists(ldif_file):
            raise CommandError(f'Datei nicht gefunden: {ldif_file}')

        self.stdout.write(f"LDIF-Datei: {ldif_file}")
        self.stdout.write(f"Dateigroesse: {os.path.getsize(ldif_file)} Bytes")

        if delete_existing:
            self.stdout.write(self.style.WARNING(
                'ACHTUNG: Bestehende Eintraege werden vor dem Import geloescht!'
            ))

        if dry_run:
            self.stdout.write(self.style.NOTICE('Dry-Run Modus - keine Aenderungen'))
            # Nur LDIF parsen und zaehlen
            with open(ldif_file, 'r') as f:
                entries = 0
                for line in f:
                    if line.startswith('dn:'):
                        entries += 1
            self.stdout.write(f'Eintraege in Datei: {entries}')
            return

        try:
            with LDAPManager() as ldap_conn:
                result = ldap_conn.import_from_ldif(ldif_file, delete_existing=delete_existing)

                if result.get('success'):
                    self.stdout.write(self.style.SUCCESS(
                        f"\nRestore erfolgreich!"
                    ))
                    self.stdout.write(f"  Importiert: {result.get('imported', 0)}")
                    self.stdout.write(f"  Uebersprungen: {result.get('skipped', 0)}")
                    self.stdout.write(f"  Fehler: {result.get('errors', 0)}")
                else:
                    raise CommandError(f"Restore fehlgeschlagen: {result.get('error', 'Unbekannt')}")

        except LDAPConnectionError as e:
            raise CommandError(f"LDAP-Verbindungsfehler: {str(e)}")
