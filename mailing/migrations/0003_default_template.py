from django.db import migrations


TEMPLATE_HTML = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; background: #f0ede4; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #1c2647; color: #ffffff; padding: 30px 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 5px 0 0; color: #e6c068; font-size: 14px; }
        .content { background-color: #ffffff; padding: 30px; }
        .greeting { font-size: 18px; color: #1c2647; margin-bottom: 20px; }
        .section { margin: 25px 0; padding: 20px; background: #f7f3e6; border-radius: 8px; border-left: 4px solid #e6c068; }
        .section h2 { color: #1c2647; font-size: 18px; margin: 0 0 10px; }
        .highlight { background: #1c2647; color: white; padding: 20px; border-radius: 8px; margin: 25px 0; text-align: center; }
        .highlight h2 { color: #e6c068; margin: 0 0 10px; }
        .highlight p { margin: 0; }
        .button { display: inline-block; padding: 12px 24px; background-color: #e6c068; color: #1c2647; text-decoration: none; border-radius: 5px; font-weight: bold; }
        .divider { border: none; border-top: 2px solid #e6c068; margin: 25px 0; }
        .footer-content { padding: 20px 30px; background: #f7f3e6; border-radius: 0 0 8px 8px; }
        .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Beispielgemeinde</h1>
            <p>Gemeindebrief</p>
        </div>
        <div class="content">
            <p class="greeting">Liebe(r) [[vorname]],</p>

            <p>wir freuen uns, Ihnen die neuesten Informationen aus unserer Gemeinde mitzuteilen.</p>

            <div class="section">
                <h2>Gottesdienste</h2>
                <p>Unsere Gottesdienste finden wie gewohnt jeden Sonntag um 10:00 Uhr statt. Wir freuen uns auf Ihr Kommen!</p>
            </div>

            <div class="section">
                <h2>Veranstaltungen</h2>
                <p>Hier koennen aktuelle Termine und Veranstaltungen eingetragen werden.</p>
                <ul>
                    <li><strong>Termin 1:</strong> Beschreibung</li>
                    <li><strong>Termin 2:</strong> Beschreibung</li>
                </ul>
            </div>

            <div class="highlight">
                <h2>Wichtige Ankuendigung</h2>
                <p>Platz fuer besondere Hinweise oder Ankuendigungen.</p>
            </div>

            <div class="section">
                <h2>Gebetsanliegen</h2>
                <p>Bitte denken Sie in Ihren Gebeten an unsere Gemeinde und die Menschen in unserer Umgebung.</p>
            </div>

            <hr class="divider">

            <p>Herzliche Gruesse,<br>
            <strong>Die Gemeindeleitung</strong><br>
            Beispielgemeinde</p>
        </div>
        <div class="footer-content">
            <p style="margin: 0; font-size: 13px; color: #555;">
                <strong>Beispielgemeinde</strong><br>
                Sie erhalten diese E-Mail als Mitglied unserer Gemeinde.
            </p>
        </div>
        <div class="footer">
            <p>&copy; 2026 Beispielgemeinde</p>
        </div>
    </div>
</body>
</html>'''


def create_default_template(apps, schema_editor):
    MailTemplate = apps.get_model('mailing', 'MailTemplate')
    if not MailTemplate.objects.filter(name='Gemeindebrief Standard').exists():
        MailTemplate.objects.create(
            name='Gemeindebrief Standard',
            subject='Neuigkeiten aus der Beispielgemeinde',
            description='Standard-Vorlage fuer Gemeindebriefe und Ankuendigungen',
            body_html=TEMPLATE_HTML,
        )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('mailing', '0002_alter_mailcampaign_recipient_type'),
    ]

    operations = [
        migrations.RunPython(create_default_template, reverse),
    ]
