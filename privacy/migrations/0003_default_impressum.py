from django.db import migrations

IMPRESSUM_HTML = '''<h3>Angaben gemaess &sect; 5 TMG</h3>
<p><strong>Beispielgemeinde e.V.</strong><br>
Gasstrasse 4<br>
32791 Lage</p>

<h3>Vertreten durch</h3>
<p>Peter Dridiger (Gemeindeleitung)</p>

<h3>Kontakt</h3>
<p>E-Mail: <a href="mailto:pastor-beispiel@example-church.de">pastor-beispiel@example-church.de</a><br>
Technik: <a href="mailto:technik@example-church.de">technik@example-church.de</a></p>

<h3>Registereintrag</h3>
<p>Registergericht: Amtsgericht Lemgo<br>
Registernummer: VR 1671</p>

<h3>Steuernummer</h3>
<p>313/5902/6868 (Finanzamt Detmold)</p>

<h3>Verantwortlich fuer den Inhalt nach &sect; 55 Abs. 2 RStV</h3>
<p>Peter Dridiger<br>
Beispielgemeinde e.V.<br>
Gasstrasse 4, 32791 Lage</p>

<h3>Haftungsausschluss</h3>

<h4>Haftung fuer Inhalte</h4>
<p>Die Inhalte unserer Seiten wurden mit groesster Sorgfalt erstellt. Fuer die Richtigkeit,
Vollstaendigkeit und Aktualitaet der Inhalte koennen wir jedoch keine Gewaehr uebernehmen.
Als Diensteanbieter sind wir gemaess &sect; 7 Abs. 1 TMG fuer eigene Inhalte auf diesen Seiten
nach den allgemeinen Gesetzen verantwortlich.</p>

<h4>Haftung fuer Links</h4>
<p>Unser Angebot enthaelt Links zu externen Webseiten Dritter, auf deren Inhalte wir keinen
Einfluss haben. Deshalb koennen wir fuer diese fremden Inhalte auch keine Gewaehr uebernehmen.</p>

<h3>Urheberrecht</h3>
<p>Die durch die Seitenbetreiber erstellten Inhalte und Werke auf diesen Seiten unterliegen
dem deutschen Urheberrecht. Die Vervielfaeltigung, Bearbeitung, Verbreitung und jede Art der
Verwertung ausserhalb der Grenzen des Urheberrechtes beduerfen der schriftlichen Zustimmung
des jeweiligen Autors bzw. Erstellers.</p>

<h3>Streitschlichtung</h3>
<p>Die Europaeische Kommission stellt eine Plattform zur Online-Streitbeilegung (OS) bereit:
<a href="https://ec.europa.eu/consumers/odr" target="_blank">https://ec.europa.eu/consumers/odr</a>.<br>
Wir sind nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer
Verbraucherschlichtungsstelle teilzunehmen.</p>'''


def create_impressum(apps, schema_editor):
    LegalPage = apps.get_model('privacy', 'LegalPage')
    if not LegalPage.objects.filter(page_type='impressum').exists():
        LegalPage.objects.create(
            page_type='impressum',
            title='Impressum',
            content_html=IMPRESSUM_HTML,
        )


class Migration(migrations.Migration):
    dependencies = [
        ('privacy', '0002_add_legalpage'),
    ]

    operations = [
        migrations.RunPython(create_impressum, migrations.RunPython.noop),
    ]
