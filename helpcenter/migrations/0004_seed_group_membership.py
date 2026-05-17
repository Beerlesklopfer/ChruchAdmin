from django.db import migrations


GROUP_MEMBERSHIP_HTML = """
<p>Gruppenmitgliedschaften steuern <strong>fast alles</strong> in dieser Anwendung &mdash; von Berechtigungen
ueber Mail-Verteiler bis zur Sichtbarkeit in der Gemeindeliste. Diese Seite erklaert, wie du Mitgliedschaften pflegst
und worauf du achten solltest.</p>

<h2>Wofuer werden Gruppen verwendet?</h2>
<p>Gruppen erfuellen in dieser Anwendung mehrere Aufgaben gleichzeitig:</p>
<table class="table table-sm table-striped">
<thead><tr><th>Gruppen-Funktion</th><th>Beispiel</th><th>Was sie bewirkt</th></tr></thead>
<tbody>
<tr><td><strong>Status</strong></td><td><code>Mitglieder</code>, <code>Besucher</code>, <code>Angehoerige</code></td><td>Bestimmt, wie ein Eintrag in Gemeindeliste, PDF-Export und Mail-Empfaengergruppen behandelt wird.</td></tr>
<tr><td><strong>Funktion</strong></td><td><code>Musik</code>, <code>Technik</code>, <code>Kassenwart</code></td><td>Bildet die Aufgaben/Teams in der Gemeinde ab. Wird oft mit einem Mail-Verteiler kombiniert.</td></tr>
<tr><td><strong>Berechtigungen</strong></td><td><code>Sekretariat</code>, <code>Leitung</code>, <code>Admins</code></td><td>Verleiht Mitgliedern Rechte (z.B. Benutzer verwalten, Mails versenden). Siehe Berechtigungs-Artikel.</td></tr>
<tr><td><strong>Mail-Verteiler</strong></td><td><code>Mitglieder</code> mit <code>mailGroup</code></td><td>Mails an die Verteiler-Adresse gehen automatisch an alle Member.</td></tr>
<tr><td><strong>Hierarchie / Bereich</strong></td><td><code>Jugend</code> mit Unter-Gruppen <code>Jugend-1..3</code></td><td>Bildet Strukturen ab. LDAP-Gruppen koennen ineinander verschachtelt sein.</td></tr>
</tbody>
</table>

<h2>Drei Wege, Mitgliedschaften zu aendern</h2>

<h3>Weg 1: Gruppen-Editor (empfohlen fuer einzelne Wechsel)</h3>
<ol>
    <li>Im Admin-Menue auf <a href="/ldap/groups/"><strong>Gruppenverwaltung</strong></a>.</li>
    <li>Gruppe per Klick oeffnen (Detail-Ansicht).</li>
    <li>Im Mitglieder-Bereich auf <em>"Mitglied hinzufuegen"</em> oder das Entfernen-Icon neben einem Member.</li>
    <li>Suchfeld nutzt Live-Suche &mdash; tippe Vor- oder Nachname.</li>
</ol>
<div class="alert alert-info small">
    Im Gruppen-Editor siehst du auch <strong>verschachtelte Gruppen</strong> &mdash; falls die Gruppe Unter-Gruppen hat,
    sind deren Mitglieder beim Mail-Verteiler automatisch dabei (Postfix expandiert ueber <code>member</code>).
</div>

<h3>Weg 2: Benutzer-Editor (empfohlen, wenn du einen Benutzer in mehreren Gruppen aendern willst)</h3>
<ol>
    <li>Im Admin-Menue auf <a href="/ldap/users/"><strong>Benutzerverwaltung</strong></a>.</li>
    <li>Benutzer waehlen, <em>"Bearbeiten"</em>.</li>
    <li>Im Editor: <strong>Status-Dropdown</strong> (Mitglied/Besucher/Gast) und <strong>Rollen-Checkboxen</strong>
        (Pastor, Aeltester, Diakon, Sekretariat) setzen.</li>
    <li>Speichern. Die Anwendung passt die LDAP-Gruppen automatisch an.</li>
</ol>
<div class="alert alert-warning small">
    <strong>Wichtig:</strong> Status-Wechsel (z.B. Besucher &rarr; Mitglied) hat Auswirkungen auf Berechtigungen,
    Mail-Verteiler und Gemeindeliste. Wer Mitglied wird, kommt automatisch in die Gruppe <code>Mitglieder</code>
    und damit auf den Verteiler <code>mitglieder@...</code>.
</div>

<h3>Weg 3: Beim Genehmigen einer Registrierung</h3>
<p>Wenn jemand sich selbst registriert (<a href="/ldap/registrations/">Registrierungsanfragen</a>), kannst du beim
Genehmigen den Status festlegen. Der neue Benutzer wird automatisch in die entsprechende Gruppe (<code>Mitglieder</code>,
<code>Besucher</code>, etc.) aufgenommen.</p>

<h2>Was passiert beim Aufnehmen / Entfernen?</h2>

<h3>Beim Hinzufuegen zu einer Gruppe</h3>
<ul>
    <li>LDAP-Attribut <code>member</code> der Gruppe bekommt einen neuen Eintrag (DN des Users).</li>
    <li>Der User sieht die Gruppe per <code>memberOf</code> in seinem Profil.</li>
    <li><strong>Sofortige Wirkung</strong>: Berechtigungen (siehe Berechtigungs-Artikel), Mail-Verteiler-Empfang, Sichtbarkeit.</li>
    <li>Eine Willkommens-E-Mail wird verschickt, wenn der Benutzer neu in <code>Mitglieder</code> aufgenommen wird.</li>
</ul>

<h3>Beim Entfernen aus einer Gruppe</h3>
<ul>
    <li><code>member</code>-Eintrag wird geloescht.</li>
    <li>User verliert sofort alle Rechte und Mail-Verteiler, die ueber diese Gruppe liefen.</li>
    <li>Bei Entfernung aus <code>Mitglieder</code> wird der User <strong>nicht</strong> automatisch geloescht &mdash; der
        Account bleibt, nur die Mitgliedschaft endet. Falls gewuenscht, danach <em>Account deaktivieren</em>
        (<code>accountDisabled=TRUE</code>) oder loeschen.</li>
</ul>

<h2>Verschachtelte Gruppen (Hierarchien)</h2>
<p>Gruppen koennen <strong>Unter-Gruppen</strong> haben, z.B.:</p>
<pre style="background:#f4f4f4; padding:0.75em; border-radius:4px; font-size:0.85em;">
ou=Groups
  cn=Mitglieder
    cn=Mitarbeiter
      cn=Musik
        cn=Musikteam-1
        cn=Musikteam-2
      cn=Technik
    cn=Leitung
      cn=Aelteste
      cn=Kassenwart
  cn=Jugend
    cn=Jugend-1
    cn=Jugend-2
</pre>
<p>Wichtig zu wissen:</p>
<ul>
    <li>Mitgliedschaft in einer Unter-Gruppe macht jemanden <strong>nicht automatisch zum Member der Eltern-Gruppe</strong>.
        Wer in <code>Musik</code> ist, ist nicht automatisch in <code>Mitarbeiter</code> &mdash; das musst du
        separat zuweisen.</li>
    <li>Beim Mail-Verteiler-Lookup expandiert Postfix nur den direkten <code>member</code>-Eintrag, nicht rekursiv.
        Wenn <code>mitarbeiter@...</code> alle Sub-Gruppen erreichen soll, muessen die User direkt in <code>Mitarbeiter</code> sein.</li>
    <li>Eltern-Gruppe loeschen geht nur, wenn keine Unter-Gruppen mehr existieren.</li>
</ul>

<h2>Spezialfaelle</h2>

<h3>Familienmitglieder</h3>
<p>Familien (Eltern/Kinder/Ehepartner) werden ueber das LDAP-Attribut <code>familyRole</code> und die
Eltern-Kind-Hierarchie im DN modelliert &mdash; <strong>nicht ueber Gruppen</strong>. Wenn ein Kind in eine Familie
aufgenommen wird, geschieht das ueber den Familien-Editor, nicht ueber den Gruppen-Editor. Status (Mitglied/Besucher)
wird zusaetzlich gesetzt.</p>

<h3>Admin-Gruppen</h3>
<p><code>Leitung</code>, <code>Admins</code> und <code>Pastor</code> sind besondere Gruppen: Mitgliedschaft darin macht
jemanden automatisch zum <em>LDAP-Admin</em> mit Zugang zum Admin-Dashboard. Sieh dir den
<a href="/hilfe/berechtigungssystem/">Berechtigungs-Artikel</a> an.</p>

<h3>Gruppen mit Mail-Adresse</h3>
<p>Wer in einer Gruppe mit <code>mailGroup</code>-Attribut ist (z.B. <code>Musik</code> &rarr; <code>musik@...</code>),
bekommt automatisch alle Mails an diese Adresse zugestellt &mdash; vorausgesetzt der User hat eine
<code>mailRoutingAddress</code> gesetzt. Verwaltung der Verteiler-Adressen unter
<a href="/ldap/mail/groups/">Mail-Verteiler</a>.</p>

<h2>Haeufige Stolpersteine</h2>
<ul>
    <li><strong>Doppel-Mitgliedschaft Mitglied + Besucher:</strong> ueber das Status-Dropdown ausgeschlossen &mdash;
        die Anwendung sorgt dafuer, dass nur ein Status gleichzeitig gilt.</li>
    <li><strong>User taucht nicht auf Mail-Verteiler auf:</strong> pruefe, ob er a) in der richtigen Gruppe ist und
        b) eine <code>mailRoutingAddress</code> + <code>mailRoutingEnabled=TRUE</code> hat. Die Mail-Uebersicht
        (<a href="/ldap/mail/">Mail-Uebersicht</a>) hilft beim Diagnostizieren.</li>
    <li><strong>Gruppe loeschen klappt nicht:</strong> es existieren noch Unter-Gruppen oder die Gruppe ist
        Mail-Verteiler. Erst die Unter-Gruppen wegnehmen und ggf. das <code>mailGroup</code>-Attribut entfernen
        (ueber Mail-Verteiler-Editor).</li>
    <li><strong>Berechtigungen wirken nicht sofort:</strong> nach einer Aenderung an
        <code>PermissionMapping</code> muss der User sich u.U. neu einloggen, damit die Anwendung die Rechte
        neu lookup-t.</li>
</ul>

<h2>Best Practices</h2>
<ul>
    <li>So wenige Sonder-Gruppen wie noetig &mdash; jede Gruppe ist Aufwand bei der Pflege.</li>
    <li>Funktions-Gruppen (Musik, Technik) klar von Status-Gruppen (Mitglieder, Besucher) trennen.</li>
    <li>Wenn eine Funktion ausschliesslich Mail-Verteiler ist (z.B. <code>info@...</code> an drei Externe), kein
        groupOfNames-Gruppe verwenden, sondern Funktions-Verteiler unter Mail-Verteiler anlegen.</li>
    <li>Aenderungen an Berechtigungs-Gruppen (<code>Leitung</code>, <code>Sekretariat</code>) im Ticket-System dokumentieren,
        damit nachvollziehbar ist, wer wann welche Rechte bekam.</li>
</ul>
"""


def seed(apps, schema_editor):
    HelpArticle = apps.get_model('helpcenter', 'HelpArticle')
    HelpArticle.objects.update_or_create(
        slug='gruppenmitgliedschaften',
        defaults={
            'title': 'Gruppenmitgliedschaften verwalten (Admin)',
            'category': 'admin',
            'summary': 'Drei Wege zur Mitgliedschaftspflege, Gruppen-Typen (Status, Funktion, Berechtigung, Mail-Verteiler), Hierarchien und haeufige Stolpersteine.',
            'content_html': GROUP_MEMBERSHIP_HTML.strip(),
            'order': 20,
            'is_published': True,
        },
    )


def unseed(apps, schema_editor):
    HelpArticle = apps.get_model('helpcenter', 'HelpArticle')
    HelpArticle.objects.filter(slug='gruppenmitgliedschaften').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('helpcenter', '0003_seed_admin_permissions'),
    ]
    operations = [
        migrations.RunPython(seed, unseed),
    ]
