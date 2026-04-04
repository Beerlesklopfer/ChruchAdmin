"""
Django Management Command für LDAP Backups
Exportiert LDAP-Daten in LDIF-Format und erstellt Backup-Historie
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from main.ldap_manager import LDAPManager, LDAPConnectionError
from authapp.models import LDAPBackup
import os
import shutil
import subprocess
from datetime import datetime


class Command(BaseCommand):
    help = 'Exportiert LDAP-Daten in LDIF-Format und erstellt Backup-Historie'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'users', 'groups', 'domains', 'schema'],
            help='Backup-Typ: full, users, groups, domains oder schema'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=str(settings.BASE_DIR / 'backups'),
            help='Verzeichnis für Backup-Dateien'
        )
        parser.add_argument(
            '--keep',
            type=int,
            default=10,
            help='Anzahl der zu behaltenden Backups (ältere werden gelöscht)'
        )
        parser.add_argument(
            '--username',
            type=str,
            default=None,
            help='Username des Benutzers der das Backup erstellt (optional)'
        )
        parser.add_argument(
            '--notes',
            type=str,
            default='',
            help='Notizen zum Backup (optional)'
        )

    def handle(self, *args, **options):
        backup_type = options['type']
        output_dir = options['output_dir']
        keep_count = options['keep']
        username = options['username']
        notes = options['notes']

        # Erstelle Output-Verzeichnis falls nicht vorhanden
        os.makedirs(output_dir, exist_ok=True)

        # Generiere Dateinamen mit Timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"ldap_backup_{backup_type}_{timestamp}.ldif"
        output_path = os.path.join(output_dir, filename)

        # Erstelle Backup-Eintrag in Datenbank
        backup = LDAPBackup.objects.create(
            backup_type=backup_type,
            filename=filename,
            file_path=output_path,
            status='running',
            notes=notes
        )

        # Setze created_by wenn Username angegeben
        if username:
            try:
                user = User.objects.get(username=username)
                backup.created_by = user
                backup.save()
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f'Benutzer {username} nicht gefunden')
                )

        self.stdout.write(f"Starte LDAP-Backup: {backup_type}")
        self.stdout.write(f"Ausgabe: {output_path}")

        try:
            # Schema-Backup (bei full oder schema)
            if backup_type in ('full', 'schema'):
                self._backup_schema(output_dir, timestamp)

            if backup_type == 'schema':
                # Nur Schema — kein Daten-Export noetig
                backup.status = 'completed'
                backup.completed_at = timezone.now()
                backup.file_size = 0
                backup.entry_count = 0
                backup.save()
                self.stdout.write(self.style.SUCCESS('Schema-Backup abgeschlossen.'))
                return

            # LDAP-Manager initialisieren
            ldap_mgr = LDAPManager()
            ldap_mgr.connect()

            # Export durchführen
            stats = ldap_mgr.export_to_ldif(
                output_path=output_path,
                backup_type=backup_type
            )

            ldap_mgr.disconnect()

            if stats['success']:
                # Aktualisiere Backup-Eintrag mit Statistiken
                backup.status = 'completed'
                backup.completed_at = timezone.now()
                backup.file_size = stats['file_size']
                backup.entry_count = stats['entry_count']
                backup.user_count = stats['user_count']
                backup.group_count = stats['group_count']
                backup.domain_count = stats['domain_count']
                backup.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Backup erfolgreich erstellt!"
                    )
                )
                self.stdout.write(f"  Einträge gesamt: {stats['entry_count']}")
                self.stdout.write(f"  Benutzer: {stats['user_count']}")
                self.stdout.write(f"  Gruppen: {stats['group_count']}")
                self.stdout.write(f"  Mail-Domains: {stats['domain_count']}")
                self.stdout.write(
                    f"  Dateigröße: {backup.get_file_size_mb()} MB"
                )
                self.stdout.write(f"  Datei: {output_path}")

                # Cleanup alte Backups
                if keep_count > 0:
                    deleted = LDAPBackup.cleanup_old_backups(keep_count)
                    if deleted > 0:
                        self.stdout.write(
                            self.style.WARNING(
                                f"\n⚠ {deleted} alte Backup(s) gelöscht (behalte {keep_count} neueste)"
                            )
                        )

            else:
                # Backup fehlgeschlagen
                backup.status = 'failed'
                backup.completed_at = timezone.now()
                backup.error_message = stats.get('error', 'Unbekannter Fehler')
                backup.save()

                raise CommandError(
                    f"Backup fehlgeschlagen: {stats.get('error', 'Unbekannter Fehler')}"
                )

        except LDAPConnectionError as e:
            backup.status = 'failed'
            backup.completed_at = timezone.now()
            backup.error_message = f"LDAP-Verbindungsfehler: {str(e)}"
            backup.save()

            raise CommandError(f"LDAP-Verbindungsfehler: {str(e)}")

        except Exception as e:
            backup.status = 'failed'
            backup.completed_at = timezone.now()
            backup.error_message = str(e)
            backup.save()

            raise CommandError(f"Fehler beim Backup: {str(e)}")

    def _backup_schema(self, output_dir, timestamp):
        """Sichert das LDAP-Schema (cn=config) und lokale Schema-Dateien"""
        schema_dir = os.path.join(output_dir, f'schema_{timestamp}')
        os.makedirs(schema_dir, exist_ok=True)

        # 1. slapcat -n0 fuer cn=config (Schema-Datenbank)
        schema_ldif = os.path.join(schema_dir, 'schema_config.ldif')
        try:
            result = subprocess.run(
                ['sudo', 'slapcat', '-n', '0'],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                with open(schema_ldif, 'w') as f:
                    f.write(result.stdout)
                self.stdout.write(self.style.SUCCESS(
                    f'  Schema (cn=config) gesichert: {schema_ldif}'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'  slapcat -n0 fehlgeschlagen (sudo noetig?): {result.stderr[:200]}'))
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.stdout.write(self.style.WARNING(f'  slapcat nicht verfuegbar: {e}'))

        # 2. Lokale Schema-LDIF-Dateien kopieren
        ldap_schema_dir = os.path.join(settings.BASE_DIR, 'ldap')
        if os.path.isdir(ldap_schema_dir):
            for f in os.listdir(ldap_schema_dir):
                if f.endswith('.ldif'):
                    src = os.path.join(ldap_schema_dir, f)
                    dst = os.path.join(schema_dir, f)
                    shutil.copy2(src, dst)
            self.stdout.write(self.style.SUCCESS(
                f'  Lokale Schema-Dateien kopiert nach {schema_dir}'))
