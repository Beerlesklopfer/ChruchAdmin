from django.db import migrations

TEMPLATE_HTML = '''<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; color: #333;">
    <div style="background-color: #1c2647; color: #ffffff; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 24px;">Willkommen bei ChurchAdmin!</h1>
        <p style="margin: 5px 0 0; color: #e6c068; font-size: 14px;">Ihr digitaler Zugang zur Bibelgemeinde Lage</p>
    </div>
    <div style="background-color: #ffffff; padding: 30px;">
        <p style="font-size: 16px;">Liebe(r) [[vorname]],</p>

        <p>wir freuen uns, Ihnen unsere neue Gemeinde-Plattform vorzustellen! Ab sofort koennen Sie viele Dinge bequem online erledigen.</p>

        <h2 style="color: #1c2647; font-size: 18px; border-bottom: 2px solid #e6c068; padding-bottom: 8px;">Was koennen Sie tun?</h2>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">&#128100; Ihr persoenliches Dashboard</h3>
            <p style="margin: 0;">Nach dem Login sehen Sie Ihr persoenliches Dashboard mit einer Uebersicht Ihrer Daten und der Gemeindeliste.</p>
        </div>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">&#128221; Profil bearbeiten</h3>
            <p style="margin: 0;">Aendern Sie Ihre Kontaktdaten wie Telefonnummer, Mobilnummer, Anschrift und Geburtstag selbst &mdash; jederzeit und ohne Umwege.</p>
        </div>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">&#128106; Familienverwaltung</h3>
            <p style="margin: 0;">Als Familienoberhaupt koennen Sie die Daten Ihrer Familienmitglieder einsehen und bearbeiten. Familienmitglieder koennen die gemeinsamen Daten ansehen.</p>
        </div>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">&#128203; Gemeindeliste</h3>
            <p style="margin: 0;">Sehen Sie die aktuelle Gemeindeliste ein und exportieren Sie diese bei Bedarf als PDF &mdash; praktisch fuer den Hauskreis oder die Gebetsliste.</p>
        </div>

        <div style="background: #f7f3e6; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 4px solid #e6c068;">
            <h3 style="color: #1c2647; margin: 0 0 8px; font-size: 15px;">&#128274; Passwort zuruecksetzen</h3>
            <p style="margin: 0;">Passwort vergessen? Kein Problem! Ueber die Login-Seite koennen Sie jederzeit ein neues Passwort anfordern. Der Link wird an Ihre private E-Mail-Adresse gesendet.</p>
        </div>

        <div style="background: #1c2647; color: white; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center;">
            <h3 style="color: #e6c068; margin: 0 0 10px;">Jetzt ausprobieren!</h3>
            <p style="margin: 0 0 15px;">Melden Sie sich an und entdecken Sie Ihre Moeglichkeiten.</p>
            <a href="https://wir.bibelgemeinde-lage.de/login/" style="display: inline-block; padding: 12px 24px; background-color: #e6c068; color: #1c2647; text-decoration: none; border-radius: 5px; font-weight: bold;">Zum Login</a>
        </div>

        <h2 style="color: #1c2647; font-size: 18px; border-bottom: 2px solid #e6c068; padding-bottom: 8px;">Gut zu wissen</h2>

        <ul style="line-height: 1.8;">
            <li>Ihre <strong>Organisations-E-Mail</strong> (@bibelgemeinde-lage.de) wird von der Gemeindeleitung verwaltet.</li>
            <li>Ihre <strong>privaten Daten</strong> (Telefon, Anschrift, etc.) koennen nur Sie selbst aendern.</li>
            <li>Alle Daten werden <strong>DSGVO-konform</strong> verarbeitet und nicht an Dritte weitergegeben.</li>
        </ul>

        <p>Bei Fragen stehen wir Ihnen gerne zur Verfuegung. Sprechen Sie uns einfach an!</p>

        <p>Herzliche Gruesse,<br><strong>Die Gemeindeleitung</strong><br>Bibelgemeinde Lage</p>
    </div>
</div>'''


def create_template(apps, schema_editor):
    MailTemplate = apps.get_model('mailing', 'MailTemplate')
    if not MailTemplate.objects.filter(name='Willkommen bei ChurchAdmin').exists():
        MailTemplate.objects.create(
            name='Willkommen bei ChurchAdmin',
            subject='Ihre neuen Moeglichkeiten bei der Bibelgemeinde Lage',
            description='Stellt Mitgliedern die Funktionen der App vor',
            body_html=TEMPLATE_HTML,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('mailing', '0006_fix_footer_default'),
    ]

    operations = [
        migrations.RunPython(create_template, migrations.RunPython.noop),
    ]
