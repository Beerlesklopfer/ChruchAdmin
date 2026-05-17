"""
Mail-Verwaltung: Domains, Uebersicht, Verteiler, Bulk-Konfiguration.
Schema-Bezug: Postfix-LDAP-Maps (virtual_mailbox_domains, virtual_group_maps).
"""
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages

from main.ldap_manager import LDAPManager, LDAPOperationError
from authapp.views import is_ldap_admin, has_permission

logger = logging.getLogger(__name__)


def _can_manage_mail_domains(user):
    return is_ldap_admin(user) or has_permission(user, 'manage_mail_domains')


def _can_manage_mail(user):
    return is_ldap_admin(user) or has_permission(user, 'manage_mail') or has_permission(user, 'manage_mail_domains')


def _decode(value):
    """LDAP-Bytes/Listen in saubere Python-Strings."""
    if value is None:
        return ''
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value.decode('latin-1', errors='replace')
    return str(value)


@login_required
@user_passes_test(_can_manage_mail)
def mail_overview(request):
    """Admin: Uebersicht aller Mail-Konfigurationen (Mailboxen + Verteiler)."""
    import ldap as ldap_mod

    domain_filter = request.GET.get('domain', '').strip().lower()
    type_filter = request.GET.get('type', '').strip()
    status_filter = request.GET.get('status', '').strip()
    q = request.GET.get('q', '').strip().lower()

    entries = []
    domains_available = []
    error = None

    try:
        with LDAPManager() as ldap_mgr:
            # Domains fuer Filter-Dropdown
            for d in ldap_mgr.list_mail_domains():
                attrs = d['attributes']
                name = attrs.get('mailDomainName') or attrs.get('dc') or ''
                if isinstance(name, list):
                    name = name[0] if name else ''
                if name:
                    domains_available.append(name)
            domains_available.sort()

            # 1) Mailboxen (User mit mail-Attribut)
            if type_filter in ('', 'mailbox'):
                user_results = ldap_mgr.conn.search_s(
                    ldap_mgr.user_search_base,
                    ldap_mod.SCOPE_SUBTREE,
                    '(&(objectClass=inetOrgPerson)(mail=*))',
                    ['cn', 'givenName', 'sn', 'mail', 'mailRoutingAddress', 'mailAliasAddress',
                     'mailQuota', 'mailRoutingEnabled', 'mailAliasEnabled', 'accountDisabled'],
                )
                for dn, attrs in user_results:
                    if not dn:
                        continue
                    cn = _decode(attrs.get('cn', [b''])[0])
                    given = _decode(attrs.get('givenName', [b''])[0])
                    sn = _decode(attrs.get('sn', [b''])[0])
                    display = f"{given} {sn}".strip() or cn
                    mails = _decode(attrs.get('mail', []))
                    if not isinstance(mails, list):
                        mails = [mails] if mails else []
                    routing = _decode(attrs.get('mailRoutingAddress', []))
                    if not isinstance(routing, list):
                        routing = [routing] if routing else []
                    aliases = _decode(attrs.get('mailAliasAddress', []))
                    if not isinstance(aliases, list):
                        aliases = [aliases] if aliases else []
                    quota = _decode(attrs.get('mailQuota', [b''])[0])
                    routing_enabled = _decode(attrs.get('mailRoutingEnabled', [b''])[0]) == 'TRUE'
                    alias_enabled = _decode(attrs.get('mailAliasEnabled', [b''])[0]) == 'TRUE'
                    account_disabled = _decode(attrs.get('accountDisabled', [b''])[0]) == 'TRUE'
                    primary = mails[0] if mails else ''
                    domain = primary.split('@', 1)[1].lower() if '@' in primary else ''
                    entries.append({
                        'type': 'mailbox',
                        'cn': cn,
                        'display': display,
                        'primary': primary,
                        'all_mails': mails,
                        'routing': routing,
                        'aliases': aliases,
                        'quota': quota,
                        'routing_enabled': routing_enabled,
                        'alias_enabled': alias_enabled,
                        'account_disabled': account_disabled,
                        'domain': domain,
                        'edit_url_name': 'ldap_user_edit',
                    })

            # 2) Verteiler (Gruppen mit mailGroup-Attribut, beide Schemata)
            if type_filter in ('', 'group'):
                group_results = ldap_mgr.conn.search_s(
                    ldap_mgr.base_dn,
                    ldap_mod.SCOPE_SUBTREE,
                    '(mailGroup=*)',
                    ['cn', 'mailGroup', 'mailRoutingAddress', 'mailRoutingEnabled',
                     'objectClass', 'member', 'description'],
                )
                for dn, attrs in group_results:
                    if not dn:
                        continue
                    cn = _decode(attrs.get('cn', [b''])[0])
                    addrs = _decode(attrs.get('mailGroup', []))
                    if not isinstance(addrs, list):
                        addrs = [addrs] if addrs else []
                    routing = _decode(attrs.get('mailRoutingAddress', []))
                    if not isinstance(routing, list):
                        routing = [routing] if routing else []
                    routing_enabled = _decode(attrs.get('mailRoutingEnabled', [b''])[0]) == 'TRUE'
                    members = attrs.get('member', [])
                    obj_classes = [_decode(c) for c in attrs.get('objectClass', [])]
                    is_group_of_names = 'groupOfNames' in obj_classes
                    is_group_mail = 'groupMail' in obj_classes
                    primary = addrs[0] if addrs else ''
                    domain = primary.split('@', 1)[1].lower() if '@' in primary else ''
                    entries.append({
                        'type': 'group',
                        'cn': cn,
                        'display': cn,
                        'primary': primary,
                        'all_mails': addrs,
                        'routing': routing,
                        'aliases': [],
                        'quota': '',
                        'routing_enabled': routing_enabled,
                        'alias_enabled': False,
                        'account_disabled': False,
                        'domain': domain,
                        'member_count': len(members) if is_group_of_names else 0,
                        'is_group_of_names': is_group_of_names,
                        'is_group_mail_obj': is_group_mail,
                        'dn': dn,
                    })

    except Exception as e:
        error = str(e)
        logger.error(f"Fehler bei Mail-Uebersicht: {e}")

    # Filter
    if domain_filter:
        entries = [e for e in entries if e['domain'] == domain_filter]
    if status_filter == 'enabled':
        entries = [e for e in entries if e['routing_enabled']]
    elif status_filter == 'disabled':
        entries = [e for e in entries if not e['routing_enabled']]
    if q:
        def matches(e):
            haystack = ' '.join([
                e.get('cn', ''), e.get('display', ''), e.get('primary', ''),
                ' '.join(e.get('all_mails', [])),
                ' '.join(e.get('routing', [])),
                ' '.join(e.get('aliases', [])),
            ]).lower()
            return q in haystack
        entries = [e for e in entries if matches(e)]

    # Sortierung: zuerst Verteiler, dann Mailboxen, jeweils alphabetisch
    entries.sort(key=lambda e: (0 if e['type'] == 'group' else 1, e['primary'].lower(), e['display'].lower()))

    stats = {
        'total': len(entries),
        'mailboxes': sum(1 for e in entries if e['type'] == 'mailbox'),
        'groups': sum(1 for e in entries if e['type'] == 'group'),
        'enabled': sum(1 for e in entries if e['routing_enabled']),
    }

    return render(request, 'ldap/mail_overview.html', {
        'entries': entries,
        'domains': domains_available,
        'stats': stats,
        'error': error,
        'filter_domain': domain_filter,
        'filter_type': type_filter,
        'filter_status': status_filter,
        'filter_q': q,
    })


@login_required
@user_passes_test(_can_manage_mail_domains)
def mail_domain_list(request):
    """Admin: Liste aller Mail-Domains mit Anzahl der Mailboxen pro Domain."""
    domains = []
    error = None
    try:
        with LDAPManager() as ldap_mgr:
            raw = ldap_mgr.list_mail_domains()
            for d in raw:
                attrs = d['attributes']
                name = attrs.get('mailDomainName') or attrs.get('dc') or ''
                if isinstance(name, list):
                    name = name[0] if name else ''
                if not name:
                    continue
                description = attrs.get('description') or ''
                if isinstance(description, list):
                    description = description[0] if description else ''
                mailbox_count = _count_mailboxes_for_domain(ldap_mgr, name)
                group_count = _count_group_mails_for_domain(ldap_mgr, name)
                domains.append({
                    'name': name,
                    'dn': d['dn'],
                    'description': description,
                    'mailbox_count': mailbox_count,
                    'group_count': group_count,
                })
            domains.sort(key=lambda x: x['name'])
    except LDAPOperationError as e:
        error = str(e)
        logger.error(f"Fehler beim Laden der Mail-Domains: {e}")

    return render(request, 'ldap/mail_domains.html', {
        'domains': domains,
        'error': error,
    })


@login_required
@user_passes_test(_can_manage_mail_domains)
def mail_domain_edit(request, domain_name):
    """Admin: Mail-Domain bearbeiten (description)."""
    if request.method != 'POST':
        return redirect('mail_domain_list')

    description = request.POST.get('description', '').strip()
    domain_dn = None

    try:
        import ldap as ldap_mod
        with LDAPManager() as ldap_mgr:
            domain_dn = f"dc={domain_name},ou=Domains,{ldap_mgr.base_dn}"
            # Aktuellen Stand holen
            results = ldap_mgr.conn.search_s(domain_dn, ldap_mod.SCOPE_BASE, '(objectClass=*)', ['description'])
            if not results or not results[0][0]:
                messages.error(request, f'Domain "{domain_name}" nicht gefunden.')
                return redirect('mail_domain_list')
            current_desc = results[0][1].get('description', [])
            mods = []
            if description:
                if current_desc:
                    mods.append((ldap_mod.MOD_REPLACE, 'description', [description.encode('utf-8')]))
                else:
                    mods.append((ldap_mod.MOD_ADD, 'description', [description.encode('utf-8')]))
            else:
                if current_desc:
                    mods.append((ldap_mod.MOD_DELETE, 'description', None))
            if mods:
                ldap_mgr.conn.modify_s(domain_dn, mods)
                messages.success(request, f'Domain "{domain_name}" aktualisiert.')
            else:
                messages.info(request, 'Keine Aenderung.')
    except Exception as e:
        messages.error(request, f'Fehler beim Speichern: {e}')
        logger.error(f"Mail-Domain-Edit fehlgeschlagen ({domain_dn}): {e}")

    return redirect('mail_domain_list')


@login_required
@user_passes_test(_can_manage_mail_domains)
def mail_domain_create(request):
    """Admin: Neue Mail-Domain anlegen (mit optionaler Beschreibung)."""
    if request.method != 'POST':
        return redirect('mail_domain_list')

    domain_name = request.POST.get('domain_name', '').strip().lower()
    description = request.POST.get('description', '').strip()

    if not domain_name:
        messages.error(request, 'Domain-Name darf nicht leer sein.')
        return redirect('mail_domain_list')

    if not _is_valid_domain(domain_name):
        messages.error(request, f'Ungueltiger Domain-Name: {domain_name}')
        return redirect('mail_domain_list')

    try:
        import ldap as ldap_mod
        with LDAPManager() as ldap_mgr:
            ldap_mgr.create_mail_domain(domain_name)
            # Description nachtraeglich setzen (LDAPManager.create_mail_domain unterstuetzt sie nicht)
            if description:
                domain_dn = f"dc={domain_name},ou=Domains,{ldap_mgr.base_dn}"
                ldap_mgr.conn.modify_s(domain_dn, [(ldap_mod.MOD_ADD, 'description', [description.encode('utf-8')])])
        messages.success(request, f'Mail-Domain "{domain_name}" wurde erstellt. Postfix-Reload nicht vergessen.')
    except LDAPOperationError as e:
        messages.error(request, f'Fehler beim Erstellen: {e}')
    except Exception as e:
        messages.error(request, f'Fehler: {e}')

    return redirect('mail_domain_list')


@login_required
@user_passes_test(_can_manage_mail_domains)
def mail_domain_delete(request, domain_name):
    """Admin: Mail-Domain loeschen."""
    if request.method != 'POST':
        return redirect('mail_domain_list')

    try:
        with LDAPManager() as ldap_mgr:
            # Sicherheitscheck: keine Domain mit aktiven Mailboxen loeschen
            mailbox_count = _count_mailboxes_for_domain(ldap_mgr, domain_name)
            if mailbox_count > 0:
                messages.error(
                    request,
                    f'Domain "{domain_name}" hat noch {mailbox_count} aktive Mailbox(en). '
                    f'Erst Benutzer-Mail-Adressen umstellen oder deaktivieren.'
                )
                return redirect('mail_domain_list')
            ldap_mgr.delete_mail_domain(domain_name)
        messages.success(request, f'Mail-Domain "{domain_name}" wurde geloescht.')
    except LDAPOperationError as e:
        messages.error(request, f'Fehler beim Loeschen: {e}')

    return redirect('mail_domain_list')


def _is_valid_domain(name):
    """Einfache Domain-Validierung (Buchstaben/Ziffern/Bindestriche/Punkte, min. 1 Punkt)."""
    import re
    if len(name) > 253 or len(name) < 3:
        return False
    if '.' not in name:
        return False
    return bool(re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$', name))


def _count_mailboxes_for_domain(ldap_mgr, domain_name):
    """Zaehle aktive Mailboxen (User mit mail=*@domain, mailRoutingEnabled=TRUE)."""
    import ldap as ldap_mod
    try:
        results = ldap_mgr.conn.search_s(
            ldap_mgr.user_search_base,
            ldap_mod.SCOPE_SUBTREE,
            f'(&(mail=*@{domain_name})(mailRoutingEnabled=TRUE))',
            ['cn'],
        )
        return len([r for r in results if r[0]])
    except Exception as e:
        logger.warning(f"Mailbox-Zaehlung fuer {domain_name} fehlgeschlagen: {e}")
        return 0


def _count_group_mails_for_domain(ldap_mgr, domain_name):
    """Zaehle aktive Gruppen-Verteiler (mailGroup=*@domain, mailRoutingEnabled=TRUE)."""
    import ldap as ldap_mod
    try:
        results = ldap_mgr.conn.search_s(
            ldap_mgr.base_dn,
            ldap_mod.SCOPE_SUBTREE,
            f'(&(mailGroup=*@{domain_name})(mailRoutingEnabled=TRUE))',
            ['cn'],
        )
        return len([r for r in results if r[0]])
    except Exception as e:
        logger.warning(f"Gruppen-Verteiler-Zaehlung fuer {domain_name} fehlgeschlagen: {e}")
        return 0


# ============================ Verteiler-Verwaltung ============================
import base64 as _b64
import re as _re

EMAIL_REGEX = _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def _b64_dn(dn):
    return _b64.urlsafe_b64encode(dn.encode('utf-8')).decode('ascii').rstrip('=')


def _unb64_dn(token):
    pad = '=' * ((4 - len(token) % 4) % 4)
    return _b64.urlsafe_b64decode(token + pad).decode('utf-8')


def _diagnose_entry(entry):
    """Liefert Liste {level, message} mit erkannten Problemen.
    Bezug: Postfix-Lookup geht ueber mailGroup=%s + mailRoutingEnabled=TRUE.
    Ohne diese zwei Attribute findet Postfix den Verteiler nicht.
    """
    issues = []
    has_mailgroup = bool(entry['mail_group'])
    has_routing = bool(entry['routing_addr'])
    enabled = entry['enabled']

    # Lookup-Schluessel fehlt
    if not has_mailgroup:
        issues.append({'level': 'danger', 'msg': 'mailGroup fehlt - Postfix kann den Verteiler nicht finden (Lookup geht ueber mailGroup=...). Adresse setzen oder Mail-Funktionalitaet entfernen.'})

    # Enable-Schalter fehlt
    if (has_mailgroup or has_routing) and not enabled:
        issues.append({'level': 'danger', 'msg': 'mailRoutingEnabled fehlt oder FALSE - Postfix verwirft Mails an diese Adresse'})

    # Funktions-Verteiler braucht zwingend Routing-Ziele
    if entry['is_func_only'] and not has_routing:
        issues.append({'level': 'warning', 'msg': 'Keine Routing-Ziele eingetragen - Mails werden zwar akzeptiert, gehen aber ins Leere'})

    # Gruppen-Verteiler: routing_addr ist redundant (Postfix expandiert ueber member)
    if entry['is_group_of_names'] and has_routing:
        issues.append({'level': 'warning', 'msg': 'Gruppen-Verteiler haben in dieser Postfix-Config kein eigenes Routing-Ziel (Mails gehen automatisch an die Member). Eintrag in mailRoutingAddress wird ignoriert.'})

    # Adress-Validierung
    for addr in entry['mail_group'] + entry['routing_addr']:
        if not EMAIL_REGEX.match(addr):
            issues.append({'level': 'warning', 'msg': f'Ungueltiger Adress-Eintrag: "{addr}"'})

    return issues


def _load_mail_groups(ldap_mgr):
    """Liefert alle Verteiler (groupOfNames mit mailGroup, plus reine groupMail-Objekte)."""
    import ldap as ldap_mod
    seen_dns = set()
    out = []
    # Alle Eintraege, die tatsaechlich Mail-Daten tragen (mailGroup oder mailRoutingAddress),
    # ausser einzelne User (inetOrgPerson). Leere groupMail-Hueellen werden ignoriert.
    results = ldap_mgr.conn.search_s(
        ldap_mgr.base_dn,
        ldap_mod.SCOPE_SUBTREE,
        '(&(|(mailGroup=*)(mailRoutingAddress=*))(!(objectClass=inetOrgPerson)))',
        ['cn', 'mailGroup', 'mailRoutingAddress', 'mailRoutingEnabled',
         'objectClass', 'member', 'description'],
    )
    for dn, attrs in results:
        if not dn or dn in seen_dns:
            continue
        seen_dns.add(dn)
        cn = (attrs.get('cn', [b''])[0] or b'').decode('utf-8', errors='replace') if attrs.get('cn') else ''
        obj_classes = [c.decode('utf-8', errors='replace') if isinstance(c, bytes) else c for c in attrs.get('objectClass', [])]
        mail_group = [v.decode('utf-8', errors='replace') if isinstance(v, bytes) else v for v in attrs.get('mailGroup', [])]
        routing_addr = [v.decode('utf-8', errors='replace') if isinstance(v, bytes) else v for v in attrs.get('mailRoutingAddress', [])]
        enabled_raw = attrs.get('mailRoutingEnabled', [b''])
        enabled = (enabled_raw[0].decode('utf-8') if enabled_raw and isinstance(enabled_raw[0], bytes) else (enabled_raw[0] if enabled_raw else '')) == 'TRUE'
        description = (attrs.get('description', [b''])[0] or b'').decode('utf-8', errors='replace') if attrs.get('description') else ''
        members = attrs.get('member', [])
        is_group_of_names = 'groupOfNames' in obj_classes
        is_group_mail = 'groupMail' in obj_classes
        primary = (mail_group[0] if mail_group else (routing_addr[0] if routing_addr else ''))
        entry = {
            'dn': dn,
            'b64dn': _b64_dn(dn),
            'cn': cn,
            'description': description,
            'mail_group': mail_group,
            'routing_addr': routing_addr,
            'enabled': enabled,
            'is_group_of_names': is_group_of_names,
            'is_group_mail': is_group_mail,
            'is_func_only': not is_group_of_names,
            'member_count': len(members),
            'object_classes': obj_classes,
            'primary': primary,
            'domain': primary.split('@', 1)[1].lower() if '@' in primary else '',
        }
        entry['issues'] = _diagnose_entry(entry)
        out.append(entry)
    out.sort(key=lambda e: (e['primary'].lower(), e['cn'].lower()))
    return out


@login_required
@user_passes_test(_can_manage_mail)
def mail_group_list(request):
    """Admin: Verteiler-Uebersicht (Funktions- und Gruppen-Verteiler) mit Diagnose."""
    entries = []
    error = None
    try:
        with LDAPManager() as ldap_mgr:
            entries = _load_mail_groups(ldap_mgr)
    except Exception as e:
        error = str(e)
        logger.error(f"Fehler bei Verteiler-Liste: {e}")

    stats = {
        'total': len(entries),
        'group': sum(1 for e in entries if e['is_group_of_names']),
        'func': sum(1 for e in entries if e['is_func_only']),
        'enabled': sum(1 for e in entries if e['enabled']),
        'with_issues': sum(1 for e in entries if e['issues']),
    }
    return render(request, 'ldap/mail_groups.html', {
        'entries': entries, 'stats': stats, 'error': error,
    })


@login_required
@user_passes_test(_can_manage_mail)
def mail_group_edit(request, b64dn):
    """Admin: Verteiler bearbeiten (mailGroup-Adressen, Routing-Ziele, Enable-Flag, Beschreibung)."""
    try:
        dn = _unb64_dn(b64dn)
    except Exception:
        messages.error(request, 'Ungueltige Verteiler-Referenz.')
        return redirect('mail_group_list')

    if request.method == 'POST':
        addresses = [a.strip() for a in request.POST.get('mail_group', '').replace(',', '\n').split('\n') if a.strip()]
        routing = [a.strip() for a in request.POST.get('routing_addr', '').replace(',', '\n').split('\n') if a.strip()]
        enabled = request.POST.get('enabled') == 'on'
        description = request.POST.get('description', '').strip()

        # Validierung
        invalid = [a for a in addresses + routing if not EMAIL_REGEX.match(a)]
        if invalid:
            messages.error(request, f'Ungueltige Adressen: {", ".join(invalid)}')
            return redirect('mail_group_edit', b64dn=b64dn)

        try:
            with LDAPManager() as ldap_mgr:
                attrs = {
                    'mailGroup': addresses if addresses else None,
                    'mailRoutingAddress': routing if routing else None,
                    'mailRoutingEnabled': 'TRUE' if enabled else 'FALSE',
                    'description': description if description else None,
                }
                # Sicherstellen: objectClass=groupMail vorhanden, wenn mailGroup gesetzt wird
                grp = ldap_mgr.get_group(dn)
                current_classes = [c.decode('utf-8') if isinstance(c, bytes) else c for c in grp['attributes'].get('objectClass', [])]
                if addresses and 'groupMail' not in current_classes:
                    import ldap as ldap_mod
                    new_classes = current_classes + ['groupMail']
                    ldap_mgr.conn.modify_s(dn, [(ldap_mod.MOD_REPLACE, 'objectClass', [c.encode('utf-8') for c in new_classes])])
                ldap_mgr.update_group(dn, attrs)
            messages.success(request, f'Verteiler aktualisiert. Postfix-Lookup-Cache braucht ggf. ein paar Minuten.')
            return redirect('mail_group_list')
        except LDAPOperationError as e:
            messages.error(request, f'Speichern fehlgeschlagen: {e}')

    # GET: aktuellen Stand laden
    try:
        with LDAPManager() as ldap_mgr:
            entries = _load_mail_groups(ldap_mgr)
            entry = next((e for e in entries if e['dn'] == dn), None)
            if not entry:
                messages.error(request, 'Verteiler nicht gefunden.')
                return redirect('mail_group_list')
            # Domains fuer Hint
            domains = [_decode(d['attributes'].get('mailDomainName') or d['attributes'].get('dc')) for d in ldap_mgr.list_mail_domains()]
            domains = [d[0] if isinstance(d, list) else d for d in domains if d]
    except Exception as e:
        messages.error(request, f'Fehler: {e}')
        return redirect('mail_group_list')

    return render(request, 'ldap/mail_group_edit.html', {
        'entry': entry, 'b64dn': b64dn, 'domains': domains,
    })


@login_required
@user_passes_test(_can_manage_mail)
def mail_group_toggle_enabled(request, b64dn):
    """Quick-Action: mailRoutingEnabled umschalten."""
    if request.method != 'POST':
        return redirect('mail_group_list')
    try:
        dn = _unb64_dn(b64dn)
        with LDAPManager() as ldap_mgr:
            grp = ldap_mgr.get_group(dn)
            current = (grp['attributes'].get('mailRoutingEnabled', [b''])[0] or b'').decode('utf-8') if grp['attributes'].get('mailRoutingEnabled') else ''
            new_val = 'FALSE' if current == 'TRUE' else 'TRUE'
            ldap_mgr.update_group(dn, {'mailRoutingEnabled': new_val})
        messages.success(request, f'Routing fuer "{dn.split(",", 1)[0]}" jetzt {new_val}.')
    except Exception as e:
        messages.error(request, f'Fehler: {e}')
    return redirect('mail_group_list')


@login_required
@user_passes_test(_can_manage_mail)
def mail_group_delete(request, b64dn):
    """Admin: Verteiler-Funktionalitaet entfernen. Bei reinem groupMail-Objekt: ganzes Objekt loeschen. Bei groupOfNames: nur Mail-Attribute strippen."""
    if request.method != 'POST':
        return redirect('mail_group_list')
    try:
        dn = _unb64_dn(b64dn)
        with LDAPManager() as ldap_mgr:
            grp = ldap_mgr.get_group(dn)
            obj_classes = [c.decode('utf-8') if isinstance(c, bytes) else c for c in grp['attributes'].get('objectClass', [])]
            cn = (grp['attributes'].get('cn', [b''])[0] or b'').decode('utf-8')
            if 'groupOfNames' in obj_classes:
                # Mail-Attribute strippen, Gruppe behalten
                import ldap as ldap_mod
                mods = []
                for attr in ('mailGroup', 'mailRoutingAddress', 'mailRoutingEnabled'):
                    if grp['attributes'].get(attr):
                        mods.append((ldap_mod.MOD_DELETE, attr, None))
                if 'groupMail' in obj_classes:
                    new_classes = [c for c in obj_classes if c != 'groupMail']
                    mods.append((ldap_mod.MOD_REPLACE, 'objectClass', [c.encode('utf-8') for c in new_classes]))
                if mods:
                    ldap_mgr.conn.modify_s(dn, mods)
                messages.success(request, f'Mail-Funktionalitaet von Gruppe "{cn}" entfernt. Gruppe selbst bleibt erhalten.')
            else:
                # Reiner Funktions-Verteiler: ganzes Objekt loeschen
                ldap_mgr.conn.delete_s(dn)
                messages.success(request, f'Funktions-Verteiler "{cn}" geloescht.')
    except Exception as e:
        messages.error(request, f'Fehler: {e}')
    return redirect('mail_group_list')


@login_required
@user_passes_test(_can_manage_mail)
def mail_group_create(request):
    """Admin: Neuen Funktions-Verteiler erstellen (eigenstaendiges groupMail-Objekt)."""
    if request.method != 'POST':
        return redirect('mail_group_list')

    cn = request.POST.get('cn', '').strip()
    addresses = [a.strip() for a in request.POST.get('mail_group', '').replace(',', '\n').split('\n') if a.strip()]
    routing = [a.strip() for a in request.POST.get('routing_addr', '').replace(',', '\n').split('\n') if a.strip()]
    description = request.POST.get('description', '').strip()
    enabled = request.POST.get('enabled') == 'on'

    if not cn or not addresses or not routing:
        messages.error(request, 'CN, mindestens eine Verteiler-Adresse und mindestens ein Routing-Ziel sind Pflicht.')
        return redirect('mail_group_list')

    invalid = [a for a in addresses + routing if not EMAIL_REGEX.match(a)]
    if invalid:
        messages.error(request, f'Ungueltige Adressen: {", ".join(invalid)}')
        return redirect('mail_group_list')

    import ldap as ldap_mod
    import ldap.modlist as modlist
    try:
        with LDAPManager() as ldap_mgr:
            new_dn = f'cn={cn},ou=Groups,{ldap_mgr.base_dn}'
            attrs = {
                'objectClass': [b'top', b'groupMail'],
                'cn': [cn.encode('utf-8')],
                'mailGroup': [a.encode('utf-8') for a in addresses],
                'mailRoutingAddress': [a.encode('utf-8') for a in routing],
                'mailRoutingEnabled': [b'TRUE' if enabled else b'FALSE'],
            }
            if description:
                attrs['description'] = [description.encode('utf-8')]
            ldap_mgr.conn.add_s(new_dn, modlist.addModlist(attrs))
        messages.success(request, f'Funktions-Verteiler "{cn}" erstellt.')
    except ldap_mod.ALREADY_EXISTS:
        messages.error(request, f'Ein Eintrag mit CN "{cn}" existiert bereits.')
    except Exception as e:
        messages.error(request, f'Fehler beim Anlegen: {e}')
    return redirect('mail_group_list')


# ============================ Bulk-Mail-Konfiguration ============================

@login_required
@user_passes_test(_can_manage_mail)
def mail_bulk(request):
    """Admin: Bulk-Aenderungen an Mailboxen (Routing-Enable, Quota, Domain-Wechsel)."""
    import ldap as ldap_mod

    # ===== POST: Aktion ausfuehren =====
    if request.method == 'POST':
        action = request.POST.get('action', '')
        target_cns = request.POST.getlist('target_cn')
        param = request.POST.get('param', '').strip()

        if not target_cns:
            messages.error(request, 'Keine Benutzer ausgewaehlt.')
            return redirect('mail_bulk')
        if action not in ('enable', 'disable', 'set_quota', 'replace_domain'):
            messages.error(request, f'Unbekannte Aktion: {action}')
            return redirect('mail_bulk')
        if action == 'set_quota' and not param.isdigit():
            messages.error(request, 'Quota muss eine ganze Zahl sein (in Bytes).')
            return redirect('mail_bulk')
        if action == 'replace_domain':
            old_new = [p.strip() for p in param.split('->')]
            if len(old_new) != 2 or not _is_valid_domain(old_new[0]) or not _is_valid_domain(old_new[1]):
                messages.error(request, 'Domain-Wechsel braucht das Format "alt.de->neu.de".')
                return redirect('mail_bulk')

        successes = 0
        failures = []
        try:
            with LDAPManager() as ldap_mgr:
                for cn in target_cns:
                    try:
                        user_dn = f'cn={cn},{ldap_mgr.user_search_base}'
                        # User suchen (case-insensitive ueber SCOPE_SUBTREE)
                        r = ldap_mgr.conn.search_s(ldap_mgr.user_search_base, ldap_mod.SCOPE_SUBTREE, f'(cn={cn})', ['mail', 'mailRoutingAddress', 'mailAliasAddress', 'mailRoutingEnabled', 'mailQuota', 'objectClass'])
                        if not r or not r[0][0]:
                            failures.append((cn, 'nicht gefunden'))
                            continue
                        user_dn, attrs = r[0]
                        mods = []
                        obj_classes = [c.decode('utf-8') if isinstance(c, bytes) else c for c in attrs.get('objectClass', [])]

                        # Sicherstellen: mailExtension-objectClass fuer Mail-Attribute
                        if action in ('enable', 'disable', 'set_quota', 'replace_domain') and 'mailExtension' not in obj_classes:
                            new_classes = obj_classes + ['mailExtension']
                            mods.append((ldap_mod.MOD_REPLACE, 'objectClass', [c.encode('utf-8') for c in new_classes]))

                        if action == 'enable':
                            mods.append((ldap_mod.MOD_REPLACE, 'mailRoutingEnabled', [b'TRUE']))
                        elif action == 'disable':
                            mods.append((ldap_mod.MOD_REPLACE, 'mailRoutingEnabled', [b'FALSE']))
                        elif action == 'set_quota':
                            mods.append((ldap_mod.MOD_REPLACE, 'mailQuota', [param.encode('utf-8')]))
                        elif action == 'replace_domain':
                            old_d, new_d = old_new
                            for attr in ('mail', 'mailRoutingAddress', 'mailAliasAddress'):
                                vals = attrs.get(attr, [])
                                if not vals:
                                    continue
                                changed = []
                                any_change = False
                                for v in vals:
                                    s = v.decode('utf-8') if isinstance(v, bytes) else v
                                    if s.lower().endswith(f'@{old_d}'):
                                        new_s = s[:-(len(old_d))] + new_d
                                        changed.append(new_s.encode('utf-8'))
                                        any_change = True
                                    else:
                                        changed.append(s.encode('utf-8') if isinstance(s, str) else s)
                                if any_change:
                                    mods.append((ldap_mod.MOD_REPLACE, attr, changed))

                        if mods:
                            ldap_mgr.conn.modify_s(user_dn, mods)
                            successes += 1
                        else:
                            failures.append((cn, 'keine Aenderung noetig'))
                    except Exception as e:
                        failures.append((cn, str(e)))
        except Exception as e:
            messages.error(request, f'LDAP-Verbindungsfehler: {e}')
            return redirect('mail_bulk')

        if successes:
            messages.success(request, f'{successes} Benutzer aktualisiert.')
        if failures:
            details = '; '.join(f'{cn}: {err}' for cn, err in failures[:5])
            more = f' (+{len(failures)-5} weitere)' if len(failures) > 5 else ''
            messages.warning(request, f'{len(failures)} fehlgeschlagen: {details}{more}')
        return redirect(f'/ldap/mail/bulk/?{request.POST.get("query_preserve", "")}')

    # ===== GET: Filter + Auswahl-Liste =====
    domain_filter = request.GET.get('domain', '').strip().lower()
    status_filter = request.GET.get('status', '').strip()
    q = request.GET.get('q', '').strip().lower()

    users = []
    domains_available = []
    error = None
    try:
        with LDAPManager() as ldap_mgr:
            for d in ldap_mgr.list_mail_domains():
                name = d['attributes'].get('mailDomainName') or d['attributes'].get('dc') or ''
                if isinstance(name, list):
                    name = name[0] if name else ''
                if name:
                    domains_available.append(name)
            domains_available.sort()

            user_results = ldap_mgr.conn.search_s(
                ldap_mgr.user_search_base,
                ldap_mod.SCOPE_SUBTREE,
                '(&(objectClass=inetOrgPerson)(|(mail=*)(mailRoutingAddress=*)))',
                ['cn', 'givenName', 'sn', 'mail', 'mailRoutingAddress', 'mailQuota', 'mailRoutingEnabled', 'accountDisabled'],
            )
            for dn, attrs in user_results:
                if not dn:
                    continue
                cn = _decode(attrs.get('cn', [b''])[0]) if attrs.get('cn') else ''
                given = _decode(attrs.get('givenName', [b''])[0]) if attrs.get('givenName') else ''
                sn = _decode(attrs.get('sn', [b''])[0]) if attrs.get('sn') else ''
                display = f'{given} {sn}'.strip() or cn
                mails = _decode(attrs.get('mail', []))
                if not isinstance(mails, list):
                    mails = [mails] if mails else []
                primary = mails[0] if mails else ''
                domain = primary.split('@', 1)[1].lower() if '@' in primary else ''
                routing_enabled = _decode(attrs.get('mailRoutingEnabled', [b''])[0]) == 'TRUE' if attrs.get('mailRoutingEnabled') else False
                quota = _decode(attrs.get('mailQuota', [b''])[0]) if attrs.get('mailQuota') else ''
                account_disabled = _decode(attrs.get('accountDisabled', [b''])[0]) == 'TRUE' if attrs.get('accountDisabled') else False
                users.append({
                    'cn': cn, 'display': display, 'primary': primary, 'domain': domain,
                    'quota': quota, 'routing_enabled': routing_enabled,
                    'all_mails': mails, 'account_disabled': account_disabled,
                })
    except Exception as e:
        error = str(e)
        logger.error(f'Bulk-Mail-Liste fehlgeschlagen: {e}')

    # Client-side filter
    if domain_filter:
        users = [u for u in users if u['domain'] == domain_filter]
    if status_filter == 'enabled':
        users = [u for u in users if u['routing_enabled']]
    elif status_filter == 'disabled':
        users = [u for u in users if not u['routing_enabled']]
    if q:
        users = [u for u in users if q in (u['cn'] + u['display'] + u['primary'] + ' '.join(u['all_mails'])).lower()]
    users.sort(key=lambda u: (u['display'].lower(), u['cn'].lower()))

    return render(request, 'ldap/mail_bulk.html', {
        'users': users, 'domains': domains_available, 'error': error,
        'filter_domain': domain_filter, 'filter_status': status_filter, 'filter_q': q,
    })
