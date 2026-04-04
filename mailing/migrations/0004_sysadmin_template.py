from django.db import migrations

TEMPLATE_HTML = '''<div style="max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif;">
    <div style="background-color: #1c2647; color: #ffffff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0; font-size: 22px;">Systembenachrichtigung</h1>
        <p style="margin: 5px 0 0; color: #e6c068; font-size: 13px;">Beispielgemeinde - IT</p>
    </div>
    <div style="background-color: #ffffff; padding: 30px;">
        <p>Liebe(r) [[vorname]],</p>

        <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <strong>Wichtiger Hinweis:</strong>
            <p style="margin: 5px 0 0;">Hier den Grund der Benachrichtigung eintragen.</p>
        </div>

        <p><strong>Was bedeutet das fuer Sie?</strong></p>
        <ul>
            <li>Punkt 1</li>
            <li>Punkt 2</li>
            <li>Punkt 3</li>
        </ul>

        <p><strong>Was muessen Sie tun?</strong></p>
        <p>Beschreiben Sie hier die erforderlichen Schritte.</p>

        <div style="background: #d1ecf1; border-left: 4px solid #0dcaf0; padding: 15px; margin: 20px 0; border-radius: 4px;">
            <strong>Bei Fragen:</strong>
            <p style="margin: 5px 0 0;">Wenden Sie sich an die IT-Administration.</p>
        </div>

        <p>Mit freundlichen Gruessen,<br><strong>IT-Administration</strong><br>Beispielgemeinde</p>
    </div>
    <div style="text-align: center; padding: 15px; font-size: 12px; color: #666;">
        <p>&copy; 2026 Beispielgemeinde</p>
    </div>
</div>'''


def create_template(apps, schema_editor):
    MailTemplate = apps.get_model('mailing', 'MailTemplate')
    if not MailTemplate.objects.filter(name='System-Benachrichtigung').exists():
        MailTemplate.objects.create(
            name='System-Benachrichtigung',
            subject='Wichtige Mitteilung - Beispielgemeinde',
            description='Fuer Sysadmins: Wartung, Aenderungen, technische Hinweise',
            body_html=TEMPLATE_HTML,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('mailing', '0003_default_template'),
    ]

    operations = [
        migrations.RunPython(create_template, migrations.RunPython.noop),
    ]
