from django.core.management.base import BaseCommand
from authapp.models import PermissionMapping


class Command(BaseCommand):
    help = 'Importiert die Standard-Berechtigungszuordnungen in die Datenbank'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Überschreibt existierende Zuordnungen',
        )

    def handle(self, *args, **options):
        # Standard-Berechtigungs-Mapping
        default_permissions = {
            'manage_users': ['Leitung', 'Admins', 'Pastor'],
            'manage_groups': ['Leitung', 'Admins'],
            'manage_families': ['Leitung', 'Admins', 'Pastor', 'Familienpflege', 'Sekretariat'],
            'manage_mail': ['Leitung', 'Admins'],
            'manage_mail_domains': ['Leitung', 'Admins'],
            'view_members': ['Leitung', 'Admins', 'Pastor', 'Mitglieder', 'Mitarbeiter', 'Sekretariat'],
            'edit_members': ['Leitung', 'Admins', 'Pastor', 'Gemeindemitarbeiter', 'Sekretariat'],
            'export_members': ['Leitung', 'Admins', 'Pastor', 'Sekretariat', 'Mitarbeiter'],
        }

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for permission, groups in default_permissions.items():
            for group_name in groups:
                # Prüfe ob Zuordnung bereits existiert
                existing = PermissionMapping.objects.filter(
                    permission=permission,
                    group_name=group_name
                ).first()

                if existing:
                    if options['overwrite']:
                        existing.is_active = True
                        existing.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Aktualisiert: {permission} → {group_name}')
                        )
                    else:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'⊘ Übersprungen (existiert): {permission} → {group_name}')
                        )
                else:
                    # Erstelle neue Zuordnung
                    PermissionMapping.objects.create(
                        permission=permission,
                        group_name=group_name,
                        is_active=True
                    )
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Erstellt: {permission} → {group_name}')
                    )

        # Zusammenfassung
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═' * 60))
        self.stdout.write(self.style.SUCCESS(f'✓ Import abgeschlossen!'))
        self.stdout.write(f'  • {created_count} neue Zuordnungen erstellt')
        self.stdout.write(f'  • {updated_count} Zuordnungen aktualisiert')
        self.stdout.write(f'  • {skipped_count} Zuordnungen übersprungen')
        self.stdout.write(self.style.SUCCESS('═' * 60))

        if skipped_count > 0 and not options['overwrite']:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING('Tipp: Verwenden Sie --overwrite um existierende Zuordnungen zu aktualisieren')
            )
