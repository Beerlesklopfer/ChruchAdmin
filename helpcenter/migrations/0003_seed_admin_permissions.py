from django.db import migrations


PERMISSIONS_HTML = """
<p>Das Berechtigungssystem hat <strong>drei Ebenen</strong>, die sich uebereinander stapeln.
Wer in einer hoeheren Ebene Rechte hat, bekommt automatisch alle Rechte der niedrigeren.</p>

<h2>Ebene 1: Django-Superuser</h2>
<p>Hoechste Stufe. Hat <strong>alle Rechte ohne Ausnahme</strong>, auch auf die Django-Admin-Oberflaeche unter
<code>/admin/</code>. Bestimmt durch das Datenbank-Flag <code>auth_user.is_superuser</code>.</p>
<div class="alert alert-warning">
    Nur fuer technische Administratoren. Andere Rollen (Pastor, Sekretariat) sollten Ebene 2 bekommen, nicht
    Superuser sein.
</div>

<h2>Ebene 2: LDAP-Admin (<code>is_ldap_admin</code>)</h2>
<p>Wer als <em>LDAP-Admin</em> gilt, kann das Admin-Dashboard, die Mail-Verwaltung, Gruppenverwaltung, Backup-Bereich,
WiFi-Konfiguration und die Hilfe-Pflege nutzen.</p>
<p>Drei Wege fuehren zum LDAP-Admin-Status:</p>
<ol>
    <li><strong>Django-Superuser-Flag</strong> (Ebene 1 erfuellt automatisch Ebene 2)</li>
    <li><strong>Mitgliedschaft in einer Django-Gruppe</strong> mit Name <code>ldap_admins</code>, <code>Leitung</code>
        oder <code>Pastor</code> (verwaltet ueber das Django-Admin-Interface)</li>
    <li><strong>LDAP-<code>memberOf</code>-Mitgliedschaft</strong> in einer Gruppe, deren DN <code>cn=Leitung</code>,
        <code>cn=Admins</code> oder <code>cn=Pastor</code> enthaelt (verwaltet im LDAP-Gruppenmodul)</li>
</ol>

<h3>So machst du jemanden zum LDAP-Admin (drei Optionen)</h3>
<div class="alert alert-secondary">
    <strong>Option A (empfohlen, einfach):</strong> Im Benutzer-Editor (<a href="/ldap/users/">LDAP-Verwaltung &rarr;
    Benutzer</a>) den Benutzer oeffnen und den <em>Superuser-Schalter</em> aktivieren. Wirkt sofort.
    <br><br>
    <strong>Option B (LDAP-konsequent):</strong> Im Gruppen-Editor (<a href="/ldap/groups/">Gruppenverwaltung</a>)
    den Benutzer der Gruppe <code>Leitung</code>, <code>Admins</code> oder <code>Pastor</code> hinzufuegen.
    Der Status wirkt nach dem naechsten Login-Refresh.
    <br><br>
    <strong>Option C (Django-Gruppe):</strong> Im Django-Admin (<a href="/admin/auth/user/">/admin/auth/user/</a>)
    den Benutzer der Django-Gruppe <code>ldap_admins</code> hinzufuegen.
</div>

<h2>Ebene 3: Granulare Berechtigungen (Permissions)</h2>
<p>Fuer Benutzer, die <em>nicht</em> Admin sein sollen, aber bestimmte Aufgaben uebernehmen (z.B. Sekretariat).
Diese Rechte werden pro LDAP-Gruppe vergeben &mdash; jeder, der in der Gruppe ist, hat die Rechte automatisch.</p>

<h3>Verfuegbare Permissions</h3>
<table class="table table-sm table-striped">
<thead><tr><th>Permission</th><th>Was sie erlaubt</th></tr></thead>
<tbody>
<tr><td><code>manage_users</code></td><td>Benutzer erstellen, bearbeiten, loeschen</td></tr>
<tr><td><code>manage_groups</code></td><td>LDAP-Gruppen verwalten und Mitglieder zuweisen</td></tr>
<tr><td><code>manage_families</code></td><td>Familienzuordnungen aendern (Eltern/Kinder/Heirat)</td></tr>
<tr><td><code>manage_mail</code></td><td>Mail-Adressen, Aliase, Routing, Quota pro Benutzer aendern</td></tr>
<tr><td><code>manage_mail_domains</code></td><td>Mail-Domains anlegen und loeschen (Postfix-Reload noetig)</td></tr>
<tr><td><code>send_massmail</code></td><td>Massen-E-Mail-Versand ueber das Mailing-Modul</td></tr>
<tr><td><code>manage_registrations</code></td><td>Registrierungsanfragen genehmigen oder ablehnen</td></tr>
<tr><td><code>view_members</code></td><td>Gemeindeliste sehen (Tabelle und PDF-Vorschau)</td></tr>
<tr><td><code>edit_members</code></td><td>Eintraege in der Gemeindeliste bearbeiten</td></tr>
<tr><td><code>export_members</code></td><td>PDF-Export der Gemeindeliste</td></tr>
</tbody>
</table>

<h3>Wo werden Permissions vergeben?</h3>
<p>In der <a href="/ldap/permissions/"><strong>Berechtigungsmatrix</strong></a> &mdash; eine Tabelle, die LDAP-Gruppen
gegen Permissions auflistet. Ein Haken in der Zelle bedeutet: alle Mitglieder dieser Gruppe haben diese Permission.</p>

<h2>Zusammenspiel im Beispiel</h2>
<div class="alert alert-info">
    <strong>Beispiel:</strong> "Sekretariat" ist eine LDAP-Gruppe. In der Berechtigungsmatrix sind fuer diese Gruppe
    die Permissions <code>manage_users</code>, <code>manage_mail</code>, <code>view_members</code>,
    <code>export_members</code> und <code>send_massmail</code> aktiviert.<br><br>
    Wer in <code>Sekretariat</code> ist, kann Benutzer pflegen, Massen-Mails verschicken und Listen exportieren &mdash;
    aber <em>keine</em> Gruppen erstellen, <em>keine</em> Backup-Dashboard ansehen und <em>keine</em>
    Mail-Domains anlegen, denn diese Bereiche sind LDAP-Admin-only.
</div>

<h2>Pruefen, welche Rechte ein Benutzer hat</h2>
<ul>
    <li>Eigene Sicht: jeder Benutzer kann seine Rechte unter <a href="/ldap/my-permissions/">Meine Berechtigungen</a>
        einsehen.</li>
    <li>Admin-Sicht: in der <a href="/ldap/permissions/">Berechtigungsmatrix</a> sieht man die Zuordnung pro Gruppe.</li>
    <li>Aus Code: <code>authapp.views.is_ldap_admin(user)</code> und
        <code>authapp.views.has_permission(user, 'manage_mail')</code>.</li>
</ul>

<h2>Sicherheitsempfehlungen</h2>
<ul>
    <li>So wenige Superuser wie moeglich &mdash; idealerweise nur ein technischer Account.</li>
    <li>LDAP-Admin-Status ueber LDAP-Gruppen (Option B) ist auditierbarer als das Superuser-Flag.</li>
    <li>Bevor du jemandem <code>manage_users</code> gibst, ueberleg ob <code>view_members</code> +
        <code>edit_members</code> reicht.</li>
    <li>Aenderungen am Berechtigungssystem sollten dokumentiert sein (Ticket-System).</li>
</ul>
"""


def seed_admin_article(apps, schema_editor):
    HelpArticle = apps.get_model('helpcenter', 'HelpArticle')
    HelpArticle.objects.update_or_create(
        slug='berechtigungssystem',
        defaults={
            'title': 'Berechtigungssystem (Admin)',
            'category': 'admin',
            'summary': 'Drei Ebenen: Superuser, LDAP-Admin, granulare Permissions. Wer kann was, wie wird jemand Admin?',
            'content_html': PERMISSIONS_HTML.strip(),
            'order': 10,
            'is_published': True,
        },
    )


def unseed_admin_article(apps, schema_editor):
    HelpArticle = apps.get_model('helpcenter', 'HelpArticle')
    HelpArticle.objects.filter(slug='berechtigungssystem').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('helpcenter', '0002_seed_mail_routing'),
    ]
    operations = [
        migrations.RunPython(seed_admin_article, unseed_admin_article),
    ]
