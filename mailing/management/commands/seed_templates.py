"""
Management Command: Erstellt/aktualisiert Standard-Mail-Vorlagen.
Aufruf: python manage.py seed_templates
Wird auch automatisch beim Deploy ausgefuehrt.
"""
from django.core.management.base import BaseCommand
from mailing.models import MailTemplate


TEMPLATES = [
    {
        'name': 'Gemeindebrief Standard',
        'subject': 'Neuigkeiten aus der Beispielgemeinde',
        'description': 'Standard-Vorlage fuer Gemeindebriefe und Ankuendigungen',
        'body_html': '''<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
    <div style="background-color: #1c2647; color: #ffffff; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px;">Beispielgemeinde</h1>
        <p style="margin: 5px 0 0; color: #e6c068; font-size: 14px;">Gemeindebrief</p>
    </div>
    <div style="background-color: #ffffff; padding: 30px; line-height: 1.6;">
        <p class="greeting" style="font-size: 16px;">Liebe(r) [[vorname]],</p>

        <p>wir freuen uns, Ihnen die neuesten Informationen aus unserer Gemeinde mitzuteilen.</p>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Gottesdienste</h3>
            <p style="margin: 0;">Unsere Gottesdienste finden wie gewohnt jeden Sonntag um 10:00 Uhr statt.</p>
        </div>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Veranstaltungen</h3>
            <ul><li><strong>Termin 1:</strong> Beschreibung</li><li><strong>Termin 2:</strong> Beschreibung</li></ul>
        </div>

        <div style="background: #1c2647; color: white; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center;">
            <h3 style="color: #e6c068; margin: 0 0 10px;">Wichtige Ankuendigung</h3>
            <p style="margin: 0;">Platz fuer besondere Hinweise.</p>
        </div>

        <p>Herzliche Gruesse,<br><strong>Die Gemeindeleitung</strong><br>Beispielgemeinde</p>
    </div>
    <div style="text-align: center; padding: 15px; font-size: 12px; color: #666;">
        <p>&copy; 2026 Beispielgemeinde</p>
    </div>
</div>''',
    },
    {
        'name': 'System-Benachrichtigung',
        'subject': 'Wichtige Mitteilung - Beispielgemeinde',
        'description': 'Fuer Sysadmins: Wartung, Aenderungen, technische Hinweise',
        'body_html': '''<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
    <div style="background-color: #1c2647; color: #ffffff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 22px;">Systembenachrichtigung</h1>
        <p style="margin: 5px 0 0; color: #e6c068; font-size: 13px;">Beispielgemeinde - IT</p>
    </div>
    <div style="background-color: #ffffff; padding: 30px; line-height: 1.6;">
        <p>Liebe(r) [[vorname]],</p>

        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <strong>Wichtiger Hinweis:</strong>
            <p style="margin: 5px 0 0;">Hier den Grund der Benachrichtigung eintragen.</p>
        </div>

        <p><strong>Was muessen Sie tun?</strong></p>
        <ul><li>Punkt 1</li><li>Punkt 2</li></ul>

        <div style="background: #d1ecf1; border-left: 4px solid #0dcaf0; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <strong>Bei Fragen:</strong>
            <p style="margin: 5px 0 0;">Wenden Sie sich an die IT-Administration.</p>
        </div>

        <p>Mit freundlichen Gruessen,<br><strong>IT-Administration</strong><br>Beispielgemeinde</p>
    </div>
    <div style="text-align: center; padding: 15px; font-size: 12px; color: #666;">
        <p>&copy; 2026 Beispielgemeinde</p>
    </div>
</div>''',
    },
    {
        'name': 'Willkommen (formal - Sie)',
        'subject': 'Ihre neuen Moeglichkeiten bei der Beispielgemeinde',
        'description': 'Formelle Vorlage mit Sie-Anrede fuer Mitglieder',
        'body_html': '''<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
    <div style="background-color: #1c2647; color: #ffffff; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px;">Willkommen bei ChurchAdmin!</h1>
        <p style="margin: 5px 0 0; color: #e6c068; font-size: 14px;">Ihr digitaler Zugang zur Beispielgemeinde</p>
    </div>
    <div style="background-color: #ffffff; padding: 30px; line-height: 1.6;">
        <p style="font-size: 16px;">Liebe(r) [[vorname]],</p>
        <p>wir freuen uns, Ihnen unsere neue Gemeinde-Plattform vorzustellen!</p>

        <h2 style="color: #1c2647; font-size: 18px; border-bottom: 2px solid #e6c068; padding-bottom: 8px;">Was koennen Sie tun?</h2>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Ihr persoenliches Dashboard</h3>
            <p style="margin: 0;">Nach dem Login sehen Sie Ihr Dashboard mit einer Uebersicht Ihrer Daten und der Gemeindeliste.</p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Profil bearbeiten</h3>
            <p style="margin: 0;">Aendern Sie Ihre Kontaktdaten selbst &mdash; jederzeit und ohne Umwege.</p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Familienverwaltung</h3>
            <p style="margin: 0;">Als Familienoberhaupt koennen Sie die Daten Ihrer Familienmitglieder verwalten.</p>
            <p style="margin: 5px 0 0; font-size: 12px; color: #666;"><em>DSGVO: Als Familienoberhaupt koennen Sie auch die Datenschutz-Einstellungen (z.B. Sichtbarkeit in der Gemeindeliste) fuer Ihre Familie verwalten.</em></p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Gemeindeliste</h3>
            <p style="margin: 0;">Sehen Sie die Gemeindeliste ein und exportieren Sie diese als PDF.</p>
            <p style="margin: 5px 0 0; font-size: 12px; color: #666;"><em>DSGVO: Welche Ihrer Daten sichtbar sind, koennen Sie in Ihren Datenschutz-Einstellungen festlegen (Opt-out moeglich).</em></p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Passwort zuruecksetzen</h3>
            <p style="margin: 0;">Ueber die Login-Seite koennen Sie jederzeit ein neues Passwort anfordern.</p>
        </div>

        <div style="background: #1c2647; color: white; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center;">
            <h3 style="color: #e6c068; margin: 0 0 10px;">Jetzt ausprobieren!</h3>
            <a href="https://wir.example-church.de/login/" style="display: inline-block; padding: 12px 24px; background-color: #e6c068; color: #1c2647; text-decoration: none; border-radius: 5px; font-weight: bold;">Zum Login</a>
        </div>

        <div style="background: #d1ecf1; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #0dcaf0;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Datenschutz (DSGVO)</h3>
            <p style="margin: 0;">Ihre Daten werden gemaess der DSGVO verarbeitet und nicht an Dritte weitergegeben. Unter <strong>Mein Profil &rarr; Meine Daten (DSGVO)</strong> koennen Sie jederzeit Ihre Daten einsehen, exportieren, Einwilligungen verwalten oder die Loeschung beantragen.</p>
        </div>

        <p>Herzliche Gruesse,<br><strong>Die Gemeindeleitung</strong><br>Beispielgemeinde</p>
    </div>
</div>''',
    },
    {
        'name': 'Willkommen (persoenlich - Du)',
        'subject': 'Deine neuen Moeglichkeiten bei der Beispielgemeinde',
        'description': 'Persoenliche Vorlage mit Du-Anrede fuer Mitglieder',
        'body_html': '''<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
    <div style="background-color: #1c2647; color: #ffffff; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px;">Willkommen bei ChurchAdmin!</h1>
        <p style="margin: 5px 0 0; color: #e6c068; font-size: 14px;">Dein digitaler Zugang zur Beispielgemeinde</p>
    </div>
    <div style="background-color: #ffffff; padding: 30px; line-height: 1.6;">
        <p style="font-size: 16px;">Hallo [[vorname]]!</p>
        <p>Schoen, dass Du dabei bist! Mit unserer neuen Plattform kannst Du viele Dinge bequem online erledigen.</p>

        <h2 style="color: #1c2647; font-size: 18px; border-bottom: 2px solid #e6c068; padding-bottom: 8px;">Was kannst Du tun?</h2>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Dein persoenliches Dashboard</h3>
            <p style="margin: 0;">Nach dem Login siehst Du Dein Dashboard mit Deinen Daten und der Gemeindeliste.</p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Profil bearbeiten</h3>
            <p style="margin: 0;">Aendere Deine Kontaktdaten selbst &mdash; jederzeit und ohne Umwege.</p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Familienverwaltung</h3>
            <p style="margin: 0;">Als Familienoberhaupt kannst Du die Daten Deiner Familie verwalten.</p>
            <p style="margin: 5px 0 0; font-size: 12px; color: #666;"><em>DSGVO: Als Familienoberhaupt kannst Du auch die Datenschutz-Einstellungen (z.B. Sichtbarkeit in der Gemeindeliste) fuer Deine Familie verwalten.</em></p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Gemeindeliste</h3>
            <p style="margin: 0;">Schau Dir die Gemeindeliste an und exportiere sie als PDF.</p>
            <p style="margin: 5px 0 0; font-size: 12px; color: #666;"><em>DSGVO: Welche Deiner Daten sichtbar sind, kannst Du in Deinen Datenschutz-Einstellungen festlegen (Opt-out moeglich).</em></p>
        </div>
        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Passwort zuruecksetzen</h3>
            <p style="margin: 0;">Ueber die Login-Seite kannst Du jederzeit ein neues Passwort anfordern.</p>
        </div>

        <div style="background: #1c2647; color: white; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center;">
            <h3 style="color: #e6c068; margin: 0 0 10px;">Jetzt ausprobieren!</h3>
            <a href="https://wir.example-church.de/login/" style="display: inline-block; padding: 12px 24px; background-color: #e6c068; color: #1c2647; text-decoration: none; border-radius: 5px; font-weight: bold;">Zum Login</a>
        </div>

        <div style="background: #d1ecf1; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #0dcaf0;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">Datenschutz (DSGVO)</h3>
            <p style="margin: 0;">Deine Daten werden gemaess der DSGVO verarbeitet und nicht an Dritte weitergegeben. Unter <strong>Mein Profil &rarr; Meine Daten (DSGVO)</strong> kannst Du jederzeit Deine Daten einsehen, exportieren, Einwilligungen verwalten oder die Loeschung beantragen.</p>
        </div>

        <p>Liebe Gruesse,<br><strong>Die Gemeindeleitung</strong><br>Beispielgemeinde</p>
    </div>
</div>''',
    },
]


class Command(BaseCommand):
    help = 'Erstellt oder aktualisiert Standard-Mail-Vorlagen'

    def handle(self, *args, **options):
        for tpl in TEMPLATES:
            obj, created = MailTemplate.objects.update_or_create(
                name=tpl['name'],
                defaults={
                    'subject': tpl['subject'],
                    'description': tpl['description'],
                    'body_html': tpl['body_html'],
                }
            )
            action = 'erstellt' if created else 'aktualisiert'
            self.stdout.write(self.style.SUCCESS(f'  {tpl["name"]} — {action}'))

        self.stdout.write(self.style.SUCCESS(f'\n{len(TEMPLATES)} Vorlagen verarbeitet.'))
