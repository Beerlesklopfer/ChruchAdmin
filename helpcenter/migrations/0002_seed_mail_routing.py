from django.db import migrations


MAIL_ROUTING_HTML = """
<p><strong>Wofuer ist diese Seite?</strong> Hier erklaeren wir, was die einzelnen Felder bei deiner E-Mail-Konfiguration bedeuten &mdash;
besonders <em>Routing-Adresse</em>, <em>Alias-Adresse</em> und der Schalter <em>aktiv</em>. Wer das versteht, kann seine E-Mails
gezielt umleiten und vermeidet, dass Mails ins Leere laufen.</p>

<h2>Die drei wichtigsten Begriffe</h2>

<h3>1. Mail (Primaeradresse)</h3>
<p>Das ist die Adresse, unter der du <strong>Mail empfangen</strong> kannst &mdash; z.B.
<code>peter.dridiger@unsere-gemeinde.de</code>. Wenn jemand an diese Adresse schreibt, wird seine Mail vom Mailserver akzeptiert
und kommt bei dir an. Du kannst mehrere Primaeradressen haben (z.B. Spitzname + voller Name).</p>

<h3>2. Routing-Adresse (Weiterleitung)</h3>
<p>Hier wird festgelegt, <strong>wohin die Mail tatsaechlich zugestellt wird</strong>. In den allermeisten Faellen ist das
deine interne Mailbox &mdash; aber du kannst hier auch eine externe Adresse eintragen, z.B. eine private
GMail-Adresse. Dann werden Mails an deine Gemeinde-Adresse automatisch dorthin weitergeleitet.</p>
<p><em>Beispiel:</em> Eingehende Mail an <code>info@unsere-gemeinde.de</code>, Routing auf <code>buero@privat.example</code> &rarr;
die Mail landet im privaten Postfach.</p>

<h3>3. Alias-Adresse</h3>
<p>Aliase sind <strong>zusaetzliche Adressen, unter denen du erreichbar bist</strong>, ohne dass eine eigene Mailbox angelegt
wird. Mails an Aliase werden zur Primaeradresse zugestellt. Typisch:
<code>p.dridiger@...</code> als Alias fuer <code>peter.dridiger@...</code>.</p>

<h2>Der wichtige Schalter: Routing aktiv</h2>
<div class="alert alert-warning">
    <strong>Wenn <code>Routing aktiv</code> auf NEIN steht, werden eingehende Mails an deine Adresse vom Server
    <em>abgewiesen</em>.</strong> Das ist Absicht: gesperrte Konten oder noch nicht freigeschaltete Adressen sollen keine Mails
    empfangen. Wenn du keine Mails bekommst &mdash; <strong>das ist der erste Schalter, den du pruefen solltest</strong>.
</div>

<h2>Wie verhalten sich die Felder zusammen?</h2>

<p>Stell dir den Mailserver wie eine Postzentrale vor:</p>
<ol>
    <li><strong>Eingang:</strong> Eine Mail kommt an <code>peter.dridiger@unsere-gemeinde.de</code>.</li>
    <li><strong>Pruefung 1 (Mailbox-Map):</strong> Existiert die Adresse als <em>Primaeradresse</em> oder <em>Alias</em>?
        Falls nein &rarr; <em>Mail Reject</em>.</li>
    <li><strong>Pruefung 2 (Routing):</strong> Ist <em>Routing aktiv</em> auf JA? Falls nein &rarr; <em>Reject</em>.</li>
    <li><strong>Zustellung:</strong> Die Routing-Adresse bestimmt, wo die Mail landet. Ohne Routing-Adresse geht die Mail in
        die interne Standard-Mailbox.</li>
</ol>

<h2>Haeufige Szenarien</h2>

<h3>Szenario A: Ich will, dass meine Gemeinde-Mails auf mein privates Postfach kommen</h3>
<ul>
    <li>Primaere Adresse: <code>vorname.nachname@unsere-gemeinde.de</code></li>
    <li>Routing-Adresse: <code>private@gmx.example</code></li>
    <li>Routing aktiv: <strong>JA</strong></li>
</ul>
<p>Vorteil: Du musst kein extra Postfach pflegen. Nachteil: Antworten gehen von der privaten Adresse aus (es sei denn,
du richtest in deinem privaten Mailprogramm "Senden als" ein).</p>

<h3>Szenario B: Ich will eine zweite Adresse fuer die gleiche Mailbox</h3>
<ul>
    <li>Primaere Adresse: <code>vorname.nachname@unsere-gemeinde.de</code></li>
    <li>Alias-Adresse: <code>v.nachname@unsere-gemeinde.de</code></li>
</ul>
<p>Beide Adressen landen in <em>einer</em> Mailbox. Praktisch fuer kurze Schreibvarianten oder Funktions-Mails (z.B.
<code>jugend@...</code> als Alias zur Mailbox des Jugendleiters).</p>

<h3>Szenario C: Ich will nicht mehr erreichbar sein, aber Konto behalten</h3>
<ul>
    <li>Routing aktiv: <strong>NEIN</strong></li>
</ul>
<p>Eingehende Mails werden abgelehnt &mdash; der Absender bekommt einen Bounce, weiss also, dass die Adresse nicht zustellbar
ist. Dein Konto bleibt aber bestehen.</p>

<h2>Worauf du achten solltest</h2>
<ul>
    <li><strong>Routing-Adresse leer lassen</strong>, wenn die Mail in der normalen internen Mailbox landen soll &mdash;
        nicht eine Kopie der eigenen Adresse eintragen, das fuehrt zu Mailschleifen.</li>
    <li>Nach einer Aenderung kann es <strong>einige Minuten dauern</strong>, bis der Mailserver die neuen Werte uebernimmt
        (interner Cache).</li>
    <li>Wenn dein Routing extern zeigt, kann es passieren, dass die externe Adresse als <em>Spam</em> markiert und blockiert wird.
        Pruefe ggf. den Spam-Ordner des Zielpostfachs.</li>
    <li>Pruefe regelmaessig deine Routing-Adresse &mdash; veraltete Adressen (alter Arbeitgeber, abgelaufene
        Mailadresse) sind eine haeufige Fehlerquelle.</li>
</ul>

<h2>Fragen?</h2>
<p>Wenn etwas unklar ist oder eine Mail nicht ankommt, melde dich beim Buero oder erstelle ein
<a href="/tickets/">Support-Ticket</a>. Bitte schreibe dabei rein: <em>An welche Adresse</em> wurde gesendet,
<em>von wem</em>, <em>wann ungefaehr</em>, und ob du eine Fehlermeldung erhalten hast.</p>
"""


GROUP_MAIL_HTML = """
<p><strong>Verteiler</strong> sind Mail-Adressen, die nicht zu einer einzelnen Person gehoeren, sondern automatisch
an <em>mehrere Empfaenger</em> verteilt werden &mdash; z.B. <code>jugend@unsere-gemeinde.de</code> an alle Jugendmitarbeiter.</p>

<h2>Zwei Sorten Verteiler</h2>

<h3>1. Gruppen-Verteiler (automatisch)</h3>
<p>Eine bestehende LDAP-Gruppe (z.B. <code>Mitarbeiter-Jugend</code>) erhaelt eine Mail-Adresse. Mails an diese Adresse werden
<strong>automatisch an alle Gruppenmitglieder</strong> weitergeleitet. Wer in die Gruppe kommt oder geht, beeinflusst den
Verteiler &mdash; ohne dass die Adresse separat gepflegt werden muss.</p>
<p><em>Vorteil:</em> immer aktuell. <em>Geeignet fuer:</em> Mitarbeiterkreise, Teams, Bereiche.</p>

<h3>2. Funktions-Verteiler (manuell)</h3>
<p>Eine Mail-Adresse, die an <strong>eine fest hinterlegte Liste externer oder interner Adressen</strong> geleitet wird.
Praktisch fuer <code>info@...</code>, das z.B. an drei feste Empfaenger geht &mdash; auch wenn diese keine Gemeinde-Mail haben.</p>

<h2>Worauf achten?</h2>
<ul>
    <li>Verteiler haben ebenfalls den Schalter <em>Routing aktiv</em>. Steht der auf NEIN, wird die Mail abgewiesen.</li>
    <li>Wer aus einer Gruppe ausscheidet, wird automatisch aus dem Verteiler entfernt &mdash; das ist Absicht.</li>
    <li>Verteiler sind <strong>keine Mailboxen</strong>: Du kannst dich nicht "in den Verteiler einloggen". Wer alle alten
        Mails sehen will, muss eine eigene Mailbox + Forwarding aufsetzen.</li>
</ul>
"""


def seed_articles(apps, schema_editor):
    HelpArticle = apps.get_model('helpcenter', 'HelpArticle')
    HelpArticle.objects.update_or_create(
        slug='mail-routing-und-forwarding',
        defaults={
            'title': 'E-Mail: Routing, Aliase und Weiterleitung verstehen',
            'category': 'mail',
            'summary': 'Was bedeuten Primaeradresse, Routing-Adresse, Alias und der Schalter "Routing aktiv"? Mit Beispielen.',
            'content_html': MAIL_ROUTING_HTML.strip(),
            'order': 10,
            'is_published': True,
        },
    )
    HelpArticle.objects.update_or_create(
        slug='mail-verteiler',
        defaults={
            'title': 'E-Mail-Verteiler (Gruppen- und Funktions-Adressen)',
            'category': 'mail',
            'summary': 'Wie Verteiler aufgebaut sind: automatische Gruppen-Verteiler vs. manuell gepflegte Funktions-Adressen.',
            'content_html': GROUP_MAIL_HTML.strip(),
            'order': 20,
            'is_published': True,
        },
    )


def unseed_articles(apps, schema_editor):
    HelpArticle = apps.get_model('helpcenter', 'HelpArticle')
    HelpArticle.objects.filter(slug__in=['mail-routing-und-forwarding', 'mail-verteiler']).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('helpcenter', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed_articles, unseed_articles),
    ]
