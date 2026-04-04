from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError
from django.conf import settings
from main.forms import CustomUserCreationForm, LdapAuthenticationForm, UserProfileForm
from authapp.models import LDAPUserLog

import ldap
import logging
from django_auth_ldap.backend import LDAPBackend

logger = logging.getLogger(__name__)

def is_ldap_admin(user):
    """
    Prüft ob Benutzer LDAP Admin Rechte hat
    Zugelassen sind:
    - Superuser
    - Mitglieder der Gruppe 'ldap_admins'
    - Mitglieder der Gruppe 'Leitung' (Pastoren wie Peter Dridiger)
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Prüfe Django-Gruppen
    if user.groups.filter(name__in=['ldap_admins', 'Leitung', 'Pastor']).exists():
        return True

    # Prüfe LDAP-Gruppenmitgliedschaften (memberOf)
    try:
        with LDAPManager() as ldap:
            user_data = ldap.get_user(user.username)
            if user_data:
                member_of = user_data['attributes'].get('memberOf', [])
                # Konvertiere bytes zu strings
                member_of_strs = []
                for group_dn in member_of:
                    if isinstance(group_dn, bytes):
                        member_of_strs.append(group_dn.decode('utf-8'))
                    else:
                        member_of_strs.append(group_dn)

                # Prüfe ob Benutzer in einer Admin-Gruppe ist
                for group_dn in member_of_strs:
                    if 'cn=Leitung' in group_dn or 'cn=Admins' in group_dn or 'cn=Pastor' in group_dn:
                        return True
    except:
        pass

    return False


def has_permission(user, permission):
    """
    Gruppenbasiertes Berechtigungssystem - liest aus Datenbank

    Berechtigungen:
    - 'manage_users': Benutzer verwalten (Erstellen, Bearbeiten, Löschen)
    - 'manage_groups': Gruppen verwalten
    - 'manage_families': Familien verwalten
    - 'manage_mail': Mail-Verwaltung
    - 'view_members': Gemeindeliste ansehen
    - 'edit_members': Gemeindeliste bearbeiten
    - 'export_members': Gemeindeliste exportieren
    """
    if not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Hole erlaubte Gruppen aus Datenbank
    from authapp.models import PermissionMapping
    allowed_groups = PermissionMapping.get_groups_for_permission(permission)

    if not allowed_groups:
        return False

    # Prüfe Django-Gruppen
    if user.groups.filter(name__in=allowed_groups).exists():
        return True

    # Prüfe LDAP-Gruppenmitgliedschaften (memberOf)
    try:
        with LDAPManager() as ldap:
            user_data = ldap.get_user(user.username)
            if user_data:
                member_of = user_data['attributes'].get('memberOf', [])
                # Extrahiere alle Gruppen-CNs
                user_groups = []
                for group_dn in member_of:
                    if isinstance(group_dn, bytes):
                        group_dn = group_dn.decode('utf-8')

                    # Extrahiere CN aus DN (z.B. cn=Leitung,ou=Groups,... -> Leitung)
                    import re
                    match = re.search(r'cn=([^,]+)', group_dn, re.IGNORECASE)
                    if match:
                        user_groups.append(match.group(1))

                # Prüfe mit PermissionMapping
                if PermissionMapping.has_permission(permission, user_groups):
                    return True
    except:
        pass

    return False


def get_family_context(username):
    """
    Ermittelt den Familien-Kontext eines Benutzers aus dem LDAP.

    Returns:
        dict mit:
        - is_head: bool - Ist der User ein Familienoberhaupt (hat Kinder)?
        - is_child: bool - Ist der User ein Kind (nested DN)?
        - head: dict oder None - Daten des Familienoberhaupts
        - children: list - Liste der Kinder
        - parent_cn: str oder None - CN des Elternteils (wenn Kind)
    """
    result = {
        'is_head': False,
        'is_child': False,
        'head': None,
        'children': [],
        'parent_cn': None,
        'family_name': '',
    }
    try:
        with LDAPManager() as ldap_conn:
            user = ldap_conn.get_user(username)
            if not user:
                return result

            user_dn = user['dn']
            attrs = user['attributes']

            def _decode(val):
                if isinstance(val, list):
                    val = val[0] if val else ''
                if isinstance(val, bytes):
                    val = val.decode('utf-8')
                return val or ''

            # Prüfe ob der User ein Kind ist (nested DN: cn=Kind,cn=Vater,ou=Users,...)
            if ',cn=' in user_dn:
                result['is_child'] = True
                parts = user_dn.split(',')
                if len(parts) >= 2 and parts[1].startswith('cn='):
                    parent_cn = parts[1][3:]
                    result['parent_cn'] = parent_cn

                    # Lade Elternteil-Daten
                    parent = ldap_conn.get_user(parent_cn)
                    if parent:
                        p_attrs = parent['attributes']
                        result['head'] = {
                            'cn': parent_cn,
                            'givenName': _decode(p_attrs.get('givenName', '')),
                            'sn': _decode(p_attrs.get('sn', '')),
                            'mail': _decode(p_attrs.get('mail', '')),
                            'telephoneNumber': _decode(p_attrs.get('telephoneNumber', '')),
                            'mobile': _decode(p_attrs.get('mobile', '')),
                            'photo_base64': ldap_conn.get_photo_as_base64(parent_cn),
                        }
                        result['family_name'] = _decode(p_attrs.get('sn', ''))

                        # Lade Geschwister
                        parent_dn = parent['dn']
                        siblings = ldap_conn.list_users(parent_dn=parent_dn)
                        for sib in siblings:
                            s_attrs = sib['attributes']
                            s_cn = _decode(s_attrs.get('cn', ''))
                            result['children'].append({
                                'cn': s_cn,
                                'givenName': _decode(s_attrs.get('givenName', '')),
                                'sn': _decode(s_attrs.get('sn', '')),
                                'mail': _decode(s_attrs.get('mail', '')),
                                'telephoneNumber': _decode(s_attrs.get('telephoneNumber', '')),
                                'mobile': _decode(s_attrs.get('mobile', '')),
                                'birthDate': _decode(s_attrs.get('birthDate', '')),
                                'photo_base64': ldap_conn.get_photo_as_base64(s_cn),
                                'is_self': s_cn == username,
                            })
            else:
                # User ist Top-Level — prüfe ob er Kinder hat
                children = ldap_conn.list_users(parent_dn=user_dn)
                if children:
                    result['is_head'] = True
                    result['family_name'] = _decode(attrs.get('sn', ''))
                    result['head'] = {
                        'cn': username,
                        'givenName': _decode(attrs.get('givenName', '')),
                        'sn': _decode(attrs.get('sn', '')),
                        'mail': _decode(attrs.get('mail', '')),
                        'telephoneNumber': _decode(attrs.get('telephoneNumber', '')),
                        'mobile': _decode(attrs.get('mobile', '')),
                        'photo_base64': ldap_conn.get_photo_as_base64(username),
                    }
                    for child in children:
                        c_attrs = child['attributes']
                        c_cn = _decode(c_attrs.get('cn', ''))
                        birth_raw = _decode(c_attrs.get('birthDate', ''))
                        birth_display = ''
                        if birth_raw:
                            try:
                                from datetime import datetime
                                birth_display = datetime.strptime(str(birth_raw)[:8], '%Y%m%d').strftime('%d.%m.%Y')
                            except (ValueError, TypeError):
                                birth_display = birth_raw
                        result['children'].append({
                            'cn': c_cn,
                            'givenName': _decode(c_attrs.get('givenName', '')),
                            'sn': _decode(c_attrs.get('sn', '')),
                            'mail': _decode(c_attrs.get('mail', '')),
                            'telephoneNumber': _decode(c_attrs.get('telephoneNumber', '')),
                            'mobile': _decode(c_attrs.get('mobile', '')),
                            'birthDate': birth_display,
                            'photo_base64': ldap_conn.get_photo_as_base64(c_cn),
                            'is_self': False,
                        })
    except Exception as e:
        logger.error(f"Fehler beim Laden des Familien-Kontexts für {username}: {e}")

    return result


def require_permission(permission):
    """Decorator für Views, die eine bestimmte Berechtigung erfordern"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if has_permission(request.user, permission):
                return view_func(request, *args, **kwargs)
            else:
                from django.http import HttpResponseForbidden
                messages.error(request, f'Sie haben keine Berechtigung für diese Aktion ({permission}).')
                return redirect('user_dashboard')
        return wrapper
    return decorator


@login_required
def ldap_profile(request):
    """LDAP Profil Anzeige"""
    try:
        # LDAP Benutzerdaten abrufen
        ldap_user = LDAPBackend().populate_user(request.user.username)
        context = {
            'ldap_user': ldap_user,
            'ldap_attrs': getattr(ldap_user, 'ldap_user', {}).attrs if ldap_user else {}
        }
    except Exception as e:
        messages.error(request, f"LDAP Fehler: {str(e)}")
        context = {'ldap_user': None}
    
    return render(request, 'ldap/profile.html', context)

@login_required
@user_passes_test(is_ldap_admin)
def ldap_admin(request):
    """LDAP Admin Dashboard"""
    stats = {
        'total_users': 0,
        'total_groups': 0,
    }
    
    try:
        # Einfache LDAP Statistik
        conn = ldap.initialize("ldap://dein-ldap-server.de")
        conn.simple_bind_s("cn=admin,dc=deine-domain,dc=de", "dein-passwort")
        
        # Benutzer zählen
        users_result = conn.search_s(
            "ou=users,dc=deine-domain,dc=de", 
            ldap.SCOPE_SUBTREE, 
            "(objectClass=inetOrgPerson)"
        )
        stats['total_users'] = len(users_result)
        
        # Gruppen zählen
        groups_result = conn.search_s(
            "ou=groups,dc=deine-domain,dc=de", 
            ldap.SCOPE_SUBTREE, 
            "(objectClass=groupOfNames)"
        )
        stats['total_groups'] = len(groups_result)
        
        conn.unbind()
        
    except Exception as e:
        messages.error(request, f"LDAP Verbindungsfehler: {str(e)}")
    
    return render(request, 'ldap/admin.html', {'stats': stats})


def _get_user_consents(cn):
    """Hole aktuellen Consent-Status eines Benutzers als komma-getrennte Strings"""
    try:
        if isinstance(cn, bytes):
            cn = cn.decode('utf-8')
        if not cn:
            return ''
        from privacy.models import ConsentLog
        from django.contrib.auth.models import User as DjangoUser
        dj_user = DjangoUser.objects.filter(username__iexact=cn).first()
        if not dj_user:
            return 'privacy_policy:true,data_processing:true,email_communication:true,member_list:true'
        result = []
        for ctype, _ in ConsentLog.CONSENT_TYPES:
            latest = ConsentLog.objects.filter(user=dj_user, consent_type=ctype).order_by('-timestamp').first()
            granted = latest.granted if latest else True
            result.append(f'{ctype}:{"true" if granted else "false"}')
        return ','.join(result)
    except Exception:
        return ''


@login_required
@user_passes_test(is_ldap_admin)
def ldap_user_search(request):
    """LDAP Benutzer Suche mit LDAPManager"""
    users = []
    all_users_for_parent = []
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    try:
        with LDAPManager() as ldap_mgr:
            # Hole alle Benutzer für Parent-Dropdown
            all_ldap_users = ldap_mgr.list_users()

            # Hole alle Gruppen für Status-Bestimmung
            groups = ldap_mgr.list_groups()

            # Erstelle Liste für Parent-Dropdown (nur Top-Level Benutzer)
            for user in all_ldap_users:
                attrs = user['attributes']

                # LDAPManager dekodiert bereits - hole Strings/Listen
                cn = attrs.get('cn', '')
                given_name = attrs.get('givenName', '')
                sn = attrs.get('sn', '')

                # Wenn Liste, hole ersten Wert
                if isinstance(cn, list):
                    cn = cn[0] if cn else ''
                if isinstance(given_name, list):
                    given_name = given_name[0] if given_name else ''
                if isinstance(sn, list):
                    sn = sn[0] if sn else ''

                # Nur Top-Level Benutzer für Parent-Auswahl
                dn = user['dn']
                if ',cn=' not in dn:  # Kein nested user
                    all_users_for_parent.append({
                        'cn': cn,
                        'givenName': given_name,
                        'sn': sn
                    })

            # Zeige alle Benutzer oder filtere nach Suchbegriff
            search_lower = search_query.lower() if search_query else ''
            for user in all_ldap_users:
                    attrs = user['attributes']

                    # Hole Attribute (LDAPManager dekodiert bereits zu Strings/Listen)
                    cn = attrs.get('cn', '')
                    uid = attrs.get('uid', '')
                    mail = attrs.get('mail', '')
                    given_name = attrs.get('givenName', '')
                    sn = attrs.get('sn', '')
                    title = attrs.get('title', '')
                    telephone = attrs.get('telephoneNumber', '')
                    mobile = attrs.get('mobile', '')
                    postal_address = attrs.get('postalAddress', '')
                    birth_date = attrs.get('birthDate', '')

                    # Attribute können String oder Liste sein - hole ersten Wert
                    if isinstance(cn, list):
                        cn = cn[0] if cn else ''
                    if isinstance(uid, list):
                        uid = uid[0] if uid else ''
                    if isinstance(mail, list):
                        mail = mail[0] if mail else ''
                    if isinstance(given_name, list):
                        given_name = given_name[0] if given_name else ''
                    if isinstance(sn, list):
                        sn = sn[0] if sn else ''
                    if isinstance(title, list):
                        title = title[0] if title else ''
                    if isinstance(telephone, list):
                        telephone = telephone[0] if telephone else ''
                    if isinstance(mobile, list):
                        mobile = mobile[0] if mobile else ''
                    if isinstance(postal_address, list):
                        postal_address = postal_address[0] if postal_address else ''
                    if isinstance(birth_date, list):
                        birth_date = birth_date[0] if birth_date else ''

                    family_role = attrs.get('familyRole', '')
                    if isinstance(family_role, list):
                        family_role = family_role[0] if family_role else ''

                    account_disabled = attrs.get('accountDisabled', '')
                    if isinstance(account_disabled, list):
                        account_disabled = account_disabled[0] if account_disabled else ''

                    # Bestimme Verwandtschaftsbeziehung aus familyRole und DN
                    dn = user['dn']
                    parent_name = None
                    parent_cn = None
                    if ',cn=' in dn:
                        parts = dn.split(',')
                        if len(parts) >= 2 and parts[1].startswith('cn='):
                            parent_cn = parts[1][3:]
                            parent_name = parent_cn.replace('.', ' ')

                    # Relationship aus familyRole bestimmen
                    if family_role == 'head':
                        relationship = 'Familienoberhaupt'
                    elif family_role == 'spouse':
                        relationship = 'Ehepartner'
                    elif family_role == 'child' or (parent_cn and not family_role):
                        relationship = 'Kind'
                    elif family_role == 'dependent':
                        relationship = 'Angehöriger'
                    else:
                        relationship = 'Mitglied'

                    # Bestimme Status aus Gruppenmitgliedschaft
                    user_dn = user['dn']
                    status = 'Nicht zugeordnet'
                    for g in groups:
                        g_attrs = g['attributes']
                        g_members = g_attrs.get('member', [])
                        g_cn = g_attrs.get('cn', '')

                        if isinstance(g_cn, list):
                            g_cn = g_cn[0] if g_cn else ''

                        # Prüfe ob Benutzer in dieser Gruppe ist
                        if user_dn in g_members:
                            if g_cn == 'Mitglieder':
                                status = 'Mitglied'
                                break
                            elif g_cn == 'Besucher':
                                status = 'Besucher'
                                break
                            elif g_cn == 'Gäste':
                                status = 'Gast'
                                break
                            elif g_cn == 'Ehepartner':
                                status = 'Ehepartner'
                                break
                            elif g_cn == 'Angehörige':
                                status = 'Angehöriger'
                                break

                    # Status-Filter anwenden
                    if status_filter:
                        if status_filter == 'Mitglieder' and status != 'Mitglied':
                            continue
                        elif status_filter == 'Besucher' and status != 'Besucher':
                            continue
                        elif status_filter == 'Gäste' and status != 'Gast':
                            continue
                        elif status_filter == 'Ehepartner' and status != 'Ehepartner':
                            continue
                        elif status_filter == 'Angehörige' and status != 'Angehöriger':
                            continue

                    # Hole Foto
                    photo_base64 = ldap_mgr.get_photo_as_base64(cn)

                    # Suche in cn, uid, mail, givenName, sn, title, relationship, parent_name, status
                    # Wenn keine Suche, zeige alle Benutzer
                    if search_query:
                        match = (
                            search_lower in cn.lower() or
                            search_lower in uid.lower() or
                            search_lower in mail.lower() or
                            search_lower in given_name.lower() or
                            search_lower in sn.lower() or
                            search_lower in title.lower() or
                            search_lower in relationship.lower() or
                            search_lower in status.lower() or
                            (parent_name and search_lower in parent_name.lower())
                        )
                    else:
                        match = True  # Zeige alle Benutzer ohne Filter

                    if match:
                        # Geburtsdatum parsen
                        birth_date_iso = ''
                        birth_date_display = ''
                        if birth_date:
                            try:
                                from datetime import datetime
                                dt = datetime.strptime(str(birth_date)[:8], '%Y%m%d')
                                birth_date_iso = dt.strftime('%Y-%m-%d')
                                birth_date_display = dt.strftime('%d.%m.%Y')
                            except (ValueError, TypeError):
                                pass

                        # Mail-Attribute (multi-value als Listen)
                        mail_list = attrs.get('mail', [])
                        if isinstance(mail_list, str):
                            mail_list = [mail_list] if mail_list else []
                        mail_routing_list = attrs.get('mailRoutingAddress', [])
                        if isinstance(mail_routing_list, str):
                            mail_routing_list = [mail_routing_list] if mail_routing_list else []
                        mail_alias_list = attrs.get('mailAliasAddress', [])
                        if isinstance(mail_alias_list, str):
                            mail_alias_list = [mail_alias_list] if mail_alias_list else []

                        mail_alias_enabled = attrs.get('mailAliasEnabled', '')
                        if isinstance(mail_alias_enabled, list):
                            mail_alias_enabled = mail_alias_enabled[0] if mail_alias_enabled else ''
                        mail_routing_enabled = attrs.get('mailRoutingEnabled', '')
                        if isinstance(mail_routing_enabled, list):
                            mail_routing_enabled = mail_routing_enabled[0] if mail_routing_enabled else ''
                        mail_quota = attrs.get('mailQuota', '')
                        if isinstance(mail_quota, list):
                            mail_quota = mail_quota[0] if mail_quota else ''

                        users.append({
                            'dn': user['dn'],
                            'uid': uid,
                            'cn': cn,
                            'mail': mail,
                            'mail_list': mail_list,
                            'mailRoutingAddress_list': mail_routing_list,
                            'mailAliasAddress_list': mail_alias_list,
                            'mailAliasEnabled': mail_alias_enabled,
                            'mailRoutingEnabled': mail_routing_enabled,
                            'mailQuota': mail_quota,
                            'givenName': given_name,
                            'sn': sn,
                            'title': title,
                            'telephoneNumber': telephone,
                            'mobile': mobile,
                            'postalAddress': postal_address,
                            'birthDate': birth_date_iso,
                            'birthDateDisplay': birth_date_display,
                            'relationship': relationship,
                            'parent_name': parent_name,
                            'parent_cn': parent_cn or '',
                            'familyRole': family_role,
                            'accountDisabled': account_disabled,
                            'photo_base64': photo_base64,
                            'status': status,
                            'consents': _get_user_consents(cn),
                        })

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP Verbindungsfehler: {str(e)}")
    except Exception as e:
        messages.error(request, f"LDAP Suchfehler: {str(e)}")

    # Pagination mit waehlbarer Seitengroesse
    from django.core.paginator import Paginator
    per_page_options = [10, 20, 50, 100]
    try:
        per_page = int(request.GET.get('per_page', 50))
        if per_page not in per_page_options:
            per_page = 50
    except (ValueError, TypeError):
        per_page = 50
    paginator = Paginator(users, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    is_mail_admin = has_permission(request.user, 'manage_mail') or request.user.is_superuser

    return render(request, 'ldap/user_search.html', {
        'users': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'search_query': search_query,
        'status_filter': status_filter,
        'all_users_for_parent': all_users_for_parent,
        'is_mail_admin': is_mail_admin,
    })

###############################################################################
# LDAP Dashboard mit Family Tree Support
###############################################################################

from main.ldap_manager import LDAPManager, LDAPConnectionError, LDAPOperationError, LDAPValidationError

@login_required
@user_passes_test(is_ldap_admin)
def ldap_dashboard(request):
    """
    LDAP Dashboard mit Statistiken und Übersicht
    Fokus auf Genealogie/Family Tree: "Wer ist mit wem verwandt"
    """
    stats = {
        'total_users': 0,
        'total_groups': 0,
        'mail_enabled': 0,
        'pending_registrations': 0,
        'members_count': 0,
        'visitors_count': 0,
        'relatives_count': 0,
        'members_percentage': 0,
        'visitors_percentage': 0,
        'relatives_percentage': 0,
        'largest_families': [],
        'mail_domains': [],
    }

    try:
        with LDAPManager() as ldap:
            # Hole alle Benutzer
            all_users = ldap.list_users()
            stats['total_users'] = len(all_users)

            # Zähle Benutzer nach Gruppen
            members_group = ldap.get_group(f"cn=Mitglieder,ou=Groups,dc=example-church,dc=de")
            visitors_group = ldap.get_group(f"cn=Besucher,ou=Groups,dc=example-church,dc=de")
            relatives_dn = f"cn=Angehörige,ou=Groups,dc=example-church,dc=de"

            if members_group:
                members = members_group['attributes'].get('member', [])
                stats['members_count'] = len([m for m in members if m != 'cn=nobody'])

            if visitors_group:
                visitors = visitors_group['attributes'].get('member', [])
                stats['visitors_count'] = len([v for v in visitors if v != 'cn=nobody'])

            # Versuche Angehörige-Gruppe zu laden
            try:
                relatives_group = ldap.get_group(relatives_dn)
                if relatives_group:
                    relatives = relatives_group['attributes'].get('member', [])
                    stats['relatives_count'] = len([r for r in relatives if r != 'cn=nobody'])
            except:
                stats['relatives_count'] = 0

            # Berechne Prozentsätze
            if stats['total_users'] > 0:
                total = stats['members_count'] + stats['visitors_count'] + stats['relatives_count']
                if total > 0:
                    stats['members_percentage'] = int((stats['members_count'] / total) * 100)
                    stats['visitors_percentage'] = int((stats['visitors_count'] / total) * 100)
                    stats['relatives_percentage'] = int((stats['relatives_count'] / total) * 100)

            # Hole Gruppen
            all_groups = ldap.list_groups()
            stats['total_groups'] = len(all_groups)

            # Zähle Mail-aktivierte Benutzer
            mail_count = 0
            for user in all_users:
                mail_enabled = user['attributes'].get('mailRoutingEnabled', [b'FALSE'])
                if isinstance(mail_enabled, list):
                    mail_enabled = mail_enabled[0]
                if mail_enabled == b'TRUE' or mail_enabled == 'TRUE':
                    mail_count += 1
            stats['mail_enabled'] = mail_count

            # Hole Mail-Domains
            try:
                domains = ldap.list_mail_domains()
                stats['mail_domains'] = [
                    d['attributes'].get('mailDomainName', [b''])[0].decode('utf-8') if isinstance(d['attributes'].get('mailDomainName', [b''])[0], bytes) else d['attributes'].get('mailDomainName', [''])[0]
                    for d in domains
                ]
            except:
                stats['mail_domains'] = []

            # Finde größte Familien (Family Tree Analysis)
            # Ein "Family Head" ist ein Benutzer mit Kindern (nested users)
            family_sizes = {}

            for user in all_users:
                user_dn = user['dn']
                cn = user['attributes'].get('cn', [b''])[0]
                if isinstance(cn, bytes):
                    cn = cn.decode('utf-8')

                # Prüfe ob dieser Benutzer Kinder hat
                children = ldap.list_users(parent_dn=user_dn)
                if children:
                    family_sizes[cn] = len(children) + 1  # +1 für den Elternteil selbst

            # Sortiere nach Familiengröße
            sorted_families = sorted(family_sizes.items(), key=lambda x: x[1], reverse=True)[:5]
            stats['largest_families'] = [
                {'name': name, 'member_count': count}
                for name, count in sorted_families
            ]

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP-Verbindungsfehler: {str(e)}")
    except Exception as e:
        messages.error(request, f"Fehler beim Laden der Statistiken: {str(e)}")

    # Hole letzte LDAP Logs
    recent_logs = LDAPUserLog.objects.all()[:10]

    # Hole Anzahl offener Registrierungsanfragen (wenn Model existiert)
    try:
        from authapp.models import RegistrationRequest
        stats['pending_registrations'] = RegistrationRequest.objects.filter(status='pending').count()
    except:
        stats['pending_registrations'] = 0

    context = {
        'stats': stats,
        'recent_logs': recent_logs,
    }

    return render(request, 'ldap/dashboard.html', context)


###############################################################################

def home(request):
    """Startseite View"""
    family = None
    if request.user.is_authenticated:
        family = get_family_context(request.user.username)
    return render(request, 'home.html', {'family': family})


@login_required
def user_dashboard(request):
    """Persönliches Dashboard für alle Benutzer"""
    user_photo_base64 = None
    ldap_user_data = None
    user_groups = []
    family = get_family_context(request.user.username)

    try:
        with LDAPManager() as ldap_conn:
            user_data = ldap_conn.get_user(request.user.username)
            if user_data:
                attrs = user_data['attributes']

                def _dec(a):
                    v = attrs.get(a, '')
                    if isinstance(v, list):
                        v = v[0] if v else ''
                    if isinstance(v, bytes):
                        v = v.decode('utf-8')
                    return v or ''

                # Alle Mail-Adressen als Listen
                def _dec_list(a):
                    vals = attrs.get(a, [])
                    if isinstance(vals, str):
                        return [vals] if vals else []
                    return [v.decode('utf-8') if isinstance(v, bytes) else v for v in vals if v]

                ldap_user_data = {
                    'cn': _dec('cn'),
                    'givenName': _dec('givenName'),
                    'sn': _dec('sn'),
                    'mail': _dec('mail'),
                    'mail_list': _dec_list('mail'),
                    'mailRoutingAddress_list': _dec_list('mailRoutingAddress'),
                    'mailAliasAddress_list': _dec_list('mailAliasAddress'),
                    'telephoneNumber': _dec('telephoneNumber'),
                    'mobile': _dec('mobile'),
                }
                user_photo_base64 = ldap_conn.get_photo_as_base64(request.user.username)

                # Gruppenmitgliedschaften
                user_dn = user_data['dn']
                groups = ldap_conn.list_groups()
                for g in groups:
                    g_attrs = g['attributes']
                    g_cn = g_attrs.get('cn', '')
                    if isinstance(g_cn, list):
                        g_cn = g_cn[0] if g_cn else ''
                    if user_dn in g_attrs.get('member', []):
                        user_groups.append(g_cn)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Dashboard-Daten: {e}")

    # Gemeindeliste laden (alle Familien + Einzelmitglieder)
    gemeinde_families = []
    gemeinde_singles = []
    if has_permission(request.user, 'view_members'):
        try:
            from privacy.models import ConsentLog as CLog
            from django.contrib.auth.models import User as DUser

            def _check_member_list_consent(cn):
                """Prueft ob Benutzer Gemeindeliste-Sichtbarkeit erlaubt (Opt-out)"""
                du = DUser.objects.filter(username__iexact=cn).first()
                if du:
                    lc = CLog.objects.filter(user=du, consent_type='member_list').order_by('-timestamp').first()
                    if lc and not lc.granted:
                        return False
                return True  # Opt-out: Default = erlaubt

            with LDAPManager() as ldap_conn2:
                all_users = ldap_conn2.list_users()
                for u in all_users:
                    u_dn = u['dn']
                    if ',cn=' in u_dn:
                        continue
                    u_attrs = u['attributes']
                    def _da(a):
                        v = u_attrs.get(a, [''])[0]
                        if isinstance(v, bytes): v = v.decode('utf-8')
                        return v or ''
                    u_cn = _da('cn')

                    # DSGVO: Gemeindeliste-Sichtbarkeit pruefen
                    if not _check_member_list_consent(u_cn):
                        continue
                    u_gn = _da('givenName')
                    u_sn = _da('sn')
                    u_mail = _da('mail')
                    u_phone = _da('telephoneNumber')
                    u_mobile = _da('mobile')
                    u_address = _da('postalAddress')
                    children = ldap_conn2.list_users(parent_dn=u_dn)
                    if children:
                        # Ehepartner und Kinder mit DSGVO-Check
                        spouse_name = ''
                        child_names = []
                        for c in children:
                            c_attrs = c['attributes']
                            c_gn = c_attrs.get('givenName', [''])[0]
                            c_sn = c_attrs.get('sn', [''])[0]
                            c_cn = c_attrs.get('cn', [''])[0]
                            c_role = c_attrs.get('familyRole', [''])[0]
                            if isinstance(c_gn, bytes): c_gn = c_gn.decode('utf-8')
                            if isinstance(c_sn, bytes): c_sn = c_sn.decode('utf-8')
                            if isinstance(c_cn, bytes): c_cn = c_cn.decode('utf-8')
                            if isinstance(c_role, bytes): c_role = c_role.decode('utf-8')
                            # DSGVO: Consent des Familienmitglieds pruefen
                            if not _check_member_list_consent(c_cn):
                                continue
                            if c_role == 'spouse':
                                spouse_name = f"{c_gn} {c_sn}"
                            else:
                                child_names.append(f"{c_gn}")
                        gemeinde_families.append({
                            'name': u_sn,
                            'head': f"{u_gn} {u_sn}",
                            'spouse': spouse_name,
                            'children': child_names,
                            'phone': u_phone,
                            'mobile': u_mobile,
                            'address': u_address,
                            'email': u_mail,
                            'member_count': len(children) + 1,
                        })
                    else:
                        gemeinde_singles.append({
                            'name': f"{u_gn} {u_sn}",
                            'phone': u_phone,
                            'mobile': u_mobile,
                            'address': u_address,
                            'email': u_mail,
                        })
                gemeinde_families.sort(key=lambda f: f['name'])
                gemeinde_singles.sort(key=lambda s: s['name'])
        except Exception as e:
            logger.error(f"Fehler beim Laden der Gemeindeliste: {e}")

    return render(request, 'dashboard/user_dashboard.html', {
        'ldap_user_data': ldap_user_data,
        'user_photo_base64': user_photo_base64,
        'user_groups': user_groups,
        'family': family,
        'is_admin': is_ldap_admin(request.user),
        'gemeinde_families': gemeinde_families,
        'gemeinde_singles': gemeinde_singles,
    })


@login_required
def family_manage(request):
    """Familienansicht: Oberhaupt kann bearbeiten, Mitglieder können ansehen"""
    family = get_family_context(request.user.username)

    if not family['is_head'] and not family['is_child']:
        messages.info(request, 'Sie sind keiner Familie zugeordnet.')
        return redirect('user_dashboard')

    return render(request, 'dashboard/family_manage.html', {
        'family': family,
    })


@login_required
def family_member_edit(request, cn):
    """Familienoberhaupt bearbeitet ein Familienmitglied"""
    family = get_family_context(request.user.username)

    # Nur Familienoberhäupter dürfen bearbeiten
    if not family['is_head']:
        messages.error(request, 'Sie haben keine Berechtigung, Familienmitglieder zu bearbeiten.')
        return redirect('user_dashboard')

    # Prüfe ob das Kind zur Familie gehört
    child_cns = [c['cn'] for c in family['children']]
    if cn not in child_cns:
        messages.error(request, 'Dieses Familienmitglied gehört nicht zu Ihrer Familie.')
        return redirect('family_manage')

    try:
        with LDAPManager() as ldap_conn:
            child = ldap_conn.get_user(cn, parent_cn=request.user.username)
            if not child:
                messages.error(request, 'Familienmitglied nicht gefunden.')
                return redirect('family_manage')

            attrs = child['attributes']
            def _dec(a):
                v = attrs.get(a, '')
                if isinstance(v, list):
                    v = v[0] if v else ''
                if isinstance(v, bytes):
                    v = v.decode('utf-8')
                return v or ''

            birth_raw = _dec('birthDate')
            birth_iso = ''
            if birth_raw:
                try:
                    from datetime import datetime
                    birth_iso = datetime.strptime(str(birth_raw)[:8], '%Y%m%d').strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    pass

            member_data = {
                'cn': cn,
                'givenName': _dec('givenName'),
                'sn': _dec('sn'),
                'mail': _dec('mail'),
                'telephoneNumber': _dec('telephoneNumber'),
                'mobile': _dec('mobile'),
                'postalAddress': _dec('postalAddress'),
                'birthDateISO': birth_iso,
                'familyRole': _dec('familyRole'),
                'photo_base64': ldap_conn.get_photo_as_base64(cn),
            }

            if request.method == 'POST':
                update_attrs = {
                    'givenName': request.POST.get('givenName', '').strip(),
                    'sn': request.POST.get('sn', '').strip(),
                }
                update_attrs['displayName'] = f"{update_attrs['givenName']} {update_attrs['sn']}"

                for field in ('telephoneNumber', 'mobile', 'postalAddress'):
                    val = request.POST.get(field, '').strip()
                    if val:
                        update_attrs[field] = val

                birth_date = request.POST.get('birthDate', '').strip()
                if birth_date:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(birth_date, '%Y-%m-%d')
                        update_attrs['birthDate'] = dt.strftime('%Y%m%d000000Z')
                    except ValueError:
                        pass

                # Familienrolle
                family_role = request.POST.get('familyRole', '').strip()
                if family_role:
                    update_attrs['familyRole'] = family_role

                photo_file = request.FILES.get('jpegPhoto')
                if photo_file:
                    try:
                        photo_bytes = ldap_conn.process_photo(photo_file)
                        update_attrs['jpegPhoto'] = photo_bytes
                    except LDAPValidationError as e:
                        messages.error(request, f'Foto-Fehler: {str(e)}')
                        return redirect('family_member_edit', cn=cn)

                ldap_conn.update_user(cn, update_attrs, parent_cn=request.user.username)
                messages.success(request, f'{update_attrs["givenName"]} wurde aktualisiert!')
                return redirect('family_manage')

    except LDAPOperationError as e:
        messages.error(request, f'LDAP-Fehler: {str(e)}')
    except Exception as e:
        messages.error(request, f'Fehler: {str(e)}')

    # DSGVO Consent-Status des Familienmitglieds laden
    from privacy.models import ConsentLog
    from django.contrib.auth.models import User as DjangoUser
    member_user = DjangoUser.objects.filter(username__iexact=cn).first()
    member_consents = {}
    for ctype, clabel in ConsentLog.CONSENT_TYPES:
        if member_user:
            latest = ConsentLog.objects.filter(user=member_user, consent_type=ctype).order_by('-timestamp').first()
            member_consents[ctype] = {'label': clabel, 'granted': latest.granted if latest else True}
        else:
            member_consents[ctype] = {'label': clabel, 'granted': True}

    # Alter pruefen: ab 16 verwaltet sich selbst
    is_minor = True
    birth_iso = member_data.get('birthDateISO', '')
    if birth_iso:
        try:
            from datetime import datetime, date
            bd = datetime.strptime(birth_iso, '%Y-%m-%d').date()
            today = date.today()
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            is_minor = age < 16
        except (ValueError, TypeError):
            pass

    return render(request, 'dashboard/family_member_edit.html', {
        'member': member_data,
        'member_consents': member_consents,
        'member_user_id': member_user.pk if member_user else None,
        'is_minor': is_minor,
    })


def _send_disabled_login_email(ldap_user_data, username, request):
    """Sendet Warn-Email an Admins bei Login-Versuch mit deaktiviertem Account"""
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.utils import timezone
        from authapp.models import PermissionMapping
        from django.contrib.auth.models import User, Group

        attrs = ldap_user_data['attributes']
        given_name = attrs.get('givenName', [''])[0] if isinstance(attrs.get('givenName', ['']), list) else attrs.get('givenName', '')
        sn = attrs.get('sn', [''])[0] if isinstance(attrs.get('sn', ['']), list) else attrs.get('sn', '')

        # Sammle Admin-E-Mail-Adressen (manage_registrations + Superuser)
        admin_emails = set()
        allowed_groups = PermissionMapping.get_groups_for_permission('manage_registrations')
        for group_name in allowed_groups:
            try:
                group = Group.objects.get(name=group_name)
                for u in group.user_set.all():
                    if u.email:
                        admin_emails.add(u.email)
            except Group.DoesNotExist:
                pass
        for u in User.objects.filter(is_superuser=True):
            if u.email:
                admin_emails.add(u.email)

        if not admin_emails:
            return

        html_message = render_to_string('emails/disabled_login_attempt.html', {
            'first_name': given_name,
            'last_name': sn,
            'username': username,
            'timestamp': timezone.now().strftime('%d.%m.%Y %H:%M:%S'),
            'ip_address': request.META.get('REMOTE_ADDR', 'unbekannt'),
        })
        plain_message = strip_tags(html_message)

        msg = EmailMultiAlternatives(
            subject=f'Sicherheitshinweis: Blockierter Login-Versuch von {given_name} {sn}',
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=list(admin_emails),
        )
        msg.attach_alternative(html_message, 'text/html')
        msg.send(fail_silently=True)
        logger.info(f"Disabled-Login-Warnung an Admins gesendet: {admin_emails} (Account: {username})")
    except Exception as e:
        logger.error(f"Fehler beim Senden der Disabled-Login-Warnung: {e}")


def ldap_login(request):
    """LDAP Login View die direkt im LDAP sucht und authentifiziert"""

    if request.method == 'POST':
        form = LdapAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')

            if not username or not password:
                messages.error(request, 'Bitte Benutzername und Passwort eingeben.')
                return render(request, 'registration/login.html')

            try:
                from django.contrib.auth.models import User
                from django.db import transaction, IntegrityError as DBIntegrityError

                # Normalisiere Username: Wenn E-Mail eingegeben wurde, hole cn aus LDAP
                normalized_username = username
                print(f"DEBUG: Original username eingegeben: {username}")

                if '@' in username:
                    # User hat vermutlich E-Mail eingegeben, suche cn in LDAP
                    print(f"DEBUG: Email erkannt, suche cn in LDAP...")
                    try:
                        import ldap
                        from main.ldap_manager import LDAPManager, LDAPConnectionError

                        ldap_mgr = LDAPManager()

                        try:
                            ldap_mgr.connect()
                            print(f"DEBUG: LDAP Connection erfolgreich")

                            # Suche User mit dieser E-Mail
                            search_filter = f"(mail={username})"
                            search_base = "ou=Users,dc=example-church,dc=de"

                            print(f"DEBUG: Suche mit Filter: {search_filter} in {search_base}")
                            result = ldap_mgr.conn.search_s(search_base, ldap.SCOPE_SUBTREE, search_filter, ['cn'])
                            print(f"DEBUG: LDAP Search Result Count: {len(result) if result else 0}")
                            print(f"DEBUG: LDAP Search Result: {result}")

                            if result and len(result) > 0:
                                # Extrahiere cn aus dem ersten Ergebnis
                                dn, attrs = result[0]
                                print(f"DEBUG: DN: {dn}, Attrs: {attrs}")
                                if 'cn' in attrs:
                                    cn_value = attrs['cn']
                                    if isinstance(cn_value, list):
                                        normalized_username = cn_value[0].decode('utf-8') if isinstance(cn_value[0], bytes) else cn_value[0]
                                    else:
                                        normalized_username = cn_value.decode('utf-8') if isinstance(cn_value, bytes) else cn_value

                                    print(f"DEBUG: Normalisierter Username: {normalized_username}")
                                    logger.info(f"Email {username} wurde zu cn {normalized_username} normalisiert")
                                else:
                                    print(f"DEBUG: 'cn' nicht in attrs gefunden!")
                            else:
                                print(f"DEBUG: Keine LDAP-Ergebnisse für email={username}")

                            ldap_mgr.disconnect()

                        except LDAPConnectionError as conn_err:
                            print(f"DEBUG: LDAP Connection fehlgeschlagen: {conn_err}")
                            logger.warning(f"LDAP Verbindung für Email-Normalisierung fehlgeschlagen: {conn_err}")
                            # Fahre mit ursprünglichem Username fort

                    except Exception as e:
                        print(f"DEBUG: Fehler bei Normalisierung: {e}")
                        import traceback
                        traceback.print_exc()
                        logger.warning(f"Konnte Email nicht zu cn normalisieren: {e}")
                        # Fahre mit ursprünglichem Username fort

                print(f"DEBUG: Verwende username für authenticate(): {normalized_username}")

                # Versuche LDAP Authentifizierung mit normalisiertem Username
                # Die authenticate() Methode erstellt automatisch den User mit dem korrekten username (cn aus LDAP)
                user = authenticate(request, username=normalized_username, password=password)

                if user is not None:
                    # Prüfe ob Account deaktiviert BEVOR login() aufgerufen wird
                    try:
                        from main.ldap_manager import LDAPManager
                        with LDAPManager() as ldap_check:
                            ldap_user_check = ldap_check.get_user(normalized_username)
                            if ldap_user_check:
                                disabled = ldap_user_check['attributes'].get('accountDisabled', [''])[0]
                                if isinstance(disabled, bytes):
                                    disabled = disabled.decode('utf-8')
                                if disabled.upper() == 'TRUE':
                                    logger.warning(f"Login blockiert: Account {normalized_username} ist deaktiviert")
                                    # Warn-Email an den Benutzer senden
                                    _send_disabled_login_email(ldap_user_check, normalized_username, request)
                                    messages.error(request, 'Ihr Zugang wurde deaktiviert. Bitte kontaktieren Sie die Gemeindeleitung.')
                                    return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})
                    except Exception as e:
                        logger.error(f"Fehler bei accountDisabled-Pruefung fuer {normalized_username}: {e}")
                        # Bei Fehler: Login trotzdem blockieren (sicherheitshalber)
                        messages.error(request, 'Anmeldung fehlgeschlagen. Bitte versuchen Sie es erneut.')
                        return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})

                    # Prüfe ob Registrierungsanfrage abgelehnt/ausstehend BEVOR login()
                    from authapp.models import RegistrationRequest
                    reg_check = RegistrationRequest.objects.filter(
                        email__iexact=user.email
                    ).order_by('-created_at').first()
                    if reg_check and reg_check.status == 'rejected':
                        messages.error(request, 'Ihr Zugang wurde abgelehnt. Bitte kontaktieren Sie die Gemeindeleitung.')
                        return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})
                    if reg_check and reg_check.status == 'pending':
                        messages.warning(request, 'Ihre Registrierungsanfrage wird noch geprueft. Bitte haben Sie etwas Geduld.')
                        return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})

                    # Alle Prüfungen bestanden - jetzt einloggen
                    login(request, user)

                    # Log erfolgreichen Login
                    LDAPUserLog.objects.create(
                        user=user,
                        action='login',
                        details=f'Erfolgreicher LDAP-Login',
                        ip_address=request.META.get('REMOTE_ADDR')
                    )

                    messages.success(request, f'Willkommen zurück, {user.get_full_name() or user.username}!')
                    next_url = request.GET.get('next') or request.POST.get('next')
                    if next_url and not (next_url.startswith('/ldap') and not is_ldap_admin(user)):
                        return redirect(next_url)
                    if is_ldap_admin(user):
                        return redirect('ldap_dashboard')
                    return redirect('user_dashboard')
                else:
                    messages.error(request, 'Ungültiger Benutzername oder Passwort.')
            except DBIntegrityError as e:
                logger.error(f"IntegrityError beim Login für {username}: {e}")

                # Workaround: Bei IntegrityError versuche direkten Login mit bestehendem User
                print(f"DEBUG: IntegrityError aufgetreten, versuche direkten User-Lookup für {normalized_username}")
                try:
                    # Finde bestehenden User - erst nach Username, dann nach Email
                    existing_user = User.objects.filter(username=normalized_username).first()

                    if not existing_user and '@' in username:
                        # Wenn kein User mit normalized_username gefunden wurde und original username eine E-Mail ist,
                        # suche nach E-Mail
                        print(f"DEBUG: Kein User mit username={normalized_username} gefunden, suche nach email={username}")
                        existing_user = User.objects.filter(email=username).first()

                        if existing_user:
                            # Verwende den echten Username des gefundenen Users
                            normalized_username = existing_user.username
                            print(f"DEBUG: User per E-Mail gefunden: {normalized_username}")

                    if existing_user:
                        # Prüfe Passwort direkt gegen LDAP
                        print(f"DEBUG: User gefunden: {existing_user.username}, prüfe LDAP Passwort...")

                        import ldap

                        try:
                            # Versuche LDAP Bind mit User Credentials
                            user_dn = f"cn={normalized_username},ou=Users,dc=example-church,dc=de"
                            print(f"DEBUG: Versuche Bind mit DN: {user_dn}")

                            # Teste Authentifizierung durch direkten Bind
                            test_conn = ldap.initialize(settings.AUTH_LDAP_SERVER_URI)
                            test_conn.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
                            test_conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
                            test_conn.simple_bind_s(user_dn, password)
                            test_conn.unbind_s()

                            print(f"DEBUG: LDAP Bind erfolgreich")

                            # Prüfe ob Account deaktiviert BEVOR login()
                            try:
                                with LDAPManager() as ldap_chk:
                                    ldap_u = ldap_chk.get_user(existing_user.username)
                                    if ldap_u:
                                        dis = ldap_u['attributes'].get('accountDisabled', [''])[0]
                                        if isinstance(dis, bytes): dis = dis.decode('utf-8')
                                        if dis.upper() == 'TRUE':
                                            logger.warning(f"Login blockiert (Pfad 2): Account {existing_user.username} ist deaktiviert")
                                            _send_disabled_login_email(ldap_u, existing_user.username, request)
                                            messages.error(request, 'Ihr Zugang wurde deaktiviert. Bitte kontaktieren Sie die Gemeindeleitung.')
                                            return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})
                            except Exception as e:
                                logger.error(f"Fehler bei accountDisabled-Pruefung (Pfad 2) fuer {existing_user.username}: {e}")
                                messages.error(request, 'Anmeldung fehlgeschlagen. Bitte versuchen Sie es erneut.')
                                return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})

                            # Prüfe Registrierungsanfrage BEVOR login()
                            from authapp.models import RegistrationRequest
                            reg_chk = RegistrationRequest.objects.filter(email__iexact=existing_user.email).order_by('-created_at').first()
                            if reg_chk and reg_chk.status == 'rejected':
                                messages.error(request, 'Ihr Zugang wurde abgelehnt. Bitte kontaktieren Sie die Gemeindeleitung.')
                                return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})
                            if reg_chk and reg_chk.status == 'pending':
                                messages.warning(request, 'Ihre Registrierungsanfrage wird noch geprueft.')
                                return render(request, 'registration/login.html', {'form': LdapAuthenticationForm()})

                            # Alle Prüfungen bestanden - jetzt einloggen
                            existing_user.backend = 'django.contrib.auth.backends.ModelBackend'
                            login(request, existing_user)

                            # Log erfolgreichen Login
                            LDAPUserLog.objects.create(
                                user=existing_user,
                                action='login',
                                details=f'Erfolgreicher LDAP-Login (Workaround nach IntegrityError)',
                                ip_address=request.META.get('REMOTE_ADDR')
                            )

                            messages.success(request, f'Willkommen zurück, {existing_user.get_full_name() or existing_user.username}!')
                            next_url = request.GET.get('next') or request.POST.get('next')
                            if next_url and not (next_url.startswith('/ldap') and not is_ldap_admin(existing_user)):
                                return redirect(next_url)
                            if is_ldap_admin(existing_user):
                                return redirect('ldap_dashboard')
                            return redirect('user_dashboard')

                        except ldap.INVALID_CREDENTIALS:
                            print(f"DEBUG: LDAP Bind fehlgeschlagen - ungültige Credentials")
                            messages.error(request, 'Ungültiger Benutzername oder Passwort.')
                        except ldap.SERVER_DOWN:
                            print(f"DEBUG: LDAP Server nicht erreichbar")
                            messages.error(request, 'LDAP Server nicht erreichbar. Bitte versuchen Sie es später erneut.')
                        except Exception as ldap_err:
                            print(f"DEBUG: LDAP Fehler: {ldap_err}")
                            import traceback
                            traceback.print_exc()
                            messages.error(request, f'LDAP Fehler: {str(ldap_err)}')
                    else:
                        print(f"DEBUG: Kein User gefunden mit username={normalized_username}")
                        messages.error(request, 'Datenbankfehler beim Login. Bitte kontaktieren Sie einen Administrator.')

                except Exception as workaround_err:
                    print(f"DEBUG: Workaround fehlgeschlagen: {workaround_err}")
                    import traceback
                    traceback.print_exc()
                    messages.error(request, 'Datenbankfehler beim Login. Bitte kontaktieren Sie einen Administrator.')
            except ldap.INVALID_CREDENTIALS:
                messages.error(request, 'Ungültige LDAP Anmeldedaten.')
            except ldap.SERVER_DOWN:
                messages.error(request, 'LDAP Server nicht erreichbar.')
            except ldap.LDAPError as e:
                messages.error(request, f'LDAP Fehler: {str(e)}')
            except Exception as e:
                print(f"!!! EXCEPTION: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()  # Detaillierter Stacktrace
                messages.error(request, f'Allgemeiner Anmeldefehler: {str(e)}')        
        else:
            # Detaillierte Fehleranalyse
            print("=== FORMULAR FEHLER ===")
            print("POST Daten:", request.POST)
            print("Form errors:", form.errors)
            print("Non-field errors:", form.non_field_errors())
            for field_name, errors in form.errors.items():
                print(f"\nFeld {field_name}: {errors} \n")            

            # Spezifische Fehlermeldung anzeigen
            if form.non_field_errors():
                for error in form.non_field_errors():
                    messages.error(request, f"Anmeldefehler: {error}")
            else:
                messages.error(request, 'Bitte überprüfen Sie Ihre Eingaben.')
    # request.method ist get
    else:
        form = LdapAuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

@require_http_methods(["GET", "POST"])
def custom_logout(request):
    """Custom Logout View die GET und POST akzeptiert"""
    logout(request)
    return redirect('home')


def register(request):
    """Registrierungsanfrage stellen"""
    from main.forms import RegistrationRequestForm
    from authapp.models import RegistrationRequest

    if request.method == 'POST':
        form = RegistrationRequestForm(request.POST)
        if form.is_valid():
            # Honeypot check (bereits in form.clean_website)
            ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or request.META.get('REMOTE_ADDR')

            # Rate Limiting: Max 3 pro IP/Stunde
            if RegistrationRequest.count_from_ip(ip) >= 3:
                messages.error(request, 'Zu viele Anfragen. Bitte versuchen Sie es spaeter erneut.')
                return render(request, 'registration/register.html', {'form': form})

            # Token generieren
            import secrets
            token = secrets.token_urlsafe(32)

            # Speichere Anfrage (Status: unverified)
            reg = RegistrationRequest.objects.create(
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email'],
                reason=form.cleaned_data['reason'],
                ip_address=ip,
                verification_token=token,
                status='unverified',
            )

            # Bestaetigungs-Mail an Antragsteller (HTML)
            try:
                from django.core.mail import EmailMultiAlternatives
                from django.template.loader import render_to_string
                from django.utils.html import strip_tags

                verify_url = request.build_absolute_uri(f'/register/verify/{token}/')
                html_message = render_to_string('emails/registration_verify.html', {
                    'first_name': reg.first_name,
                    'verify_url': verify_url,
                })
                plain_message = strip_tags(html_message)

                msg = EmailMultiAlternatives(
                    subject='E-Mail-Adresse bestaetigen - Beispielgemeinde',
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[reg.email],
                )
                msg.attach_alternative(html_message, 'text/html')
                msg.send(fail_silently=False)
            except Exception:
                pass

            messages.success(request, 'Bitte pruefen Sie Ihr E-Mail-Postfach und bestaetigen Sie Ihre E-Mail-Adresse.')
            return redirect('login')
    else:
        form = RegistrationRequestForm()

    return render(request, 'registration/register.html', {'form': form})


def register_verify(request, token):
    """E-Mail-Adresse bestaetigen"""
    from authapp.models import RegistrationRequest
    from django.utils import timezone
    from datetime import timedelta

    try:
        reg = RegistrationRequest.objects.get(verification_token=token, status='unverified')
    except RegistrationRequest.DoesNotExist:
        messages.error(request, 'Ungueltiger oder bereits verwendeter Bestaetigungslink.')
        return redirect('login')

    # 24h Ablauf pruefen
    if timezone.now() - reg.created_at > timedelta(hours=24):
        messages.error(request, 'Dieser Bestaetigungslink ist abgelaufen. Bitte stellen Sie eine neue Anfrage.')
        reg.delete()
        return redirect('register')

    reg.email_verified = True
    reg.status = 'pending'
    reg.save()

    # Mail an alle User mit manage_users-Berechtigung
    try:
        from authapp.models import PermissionMapping
        from django.contrib.auth.models import User, Group
        from django.core.mail import send_mail

        # Finde alle Gruppen mit manage_users-Berechtigung
        allowed_groups = PermissionMapping.get_groups_for_permission('manage_registrations')
        # Finde alle Django-User in diesen Gruppen + Superuser
        recipient_emails = set()
        for group_name in allowed_groups:
            try:
                group = Group.objects.get(name=group_name)
                for u in group.user_set.all():
                    if u.email:
                        recipient_emails.add(u.email)
            except Group.DoesNotExist:
                pass
        for u in User.objects.filter(is_superuser=True):
            if u.email:
                recipient_emails.add(u.email)

        if recipient_emails:
            send_mail(
                f'Neue Registrierungsanfrage: {reg.first_name} {reg.last_name}',
                f'Name: {reg.first_name} {reg.last_name}\n'
                f'E-Mail: {reg.email} (bestaetigt)\n'
                f'Begruendung: {reg.reason}\n\n'
                f'Bitte pruefen unter: /ldap/registrations/',
                settings.DEFAULT_FROM_EMAIL,
                list(recipient_emails),
                fail_silently=True,
            )
    except Exception:
        pass

    messages.success(request, 'E-Mail-Adresse bestaetigt! Ihre Anfrage wird jetzt von der Gemeindeleitung geprueft.')
    return redirect('login')


@login_required
@require_permission('manage_registrations')
def registration_delete(request, pk):
    """Registrierungsanfrage loeschen"""
    from authapp.models import RegistrationRequest
    reg = RegistrationRequest.objects.get(pk=pk)
    if request.method == 'POST':
        name = f"{reg.first_name} {reg.last_name}"
        reg.delete()
        messages.success(request, f'Anfrage von {name} wurde geloescht.')
    return redirect('registration_requests')


@login_required
@require_permission('manage_registrations')
def registration_requests(request):
    """Liste aller Registrierungsanfragen"""
    from authapp.models import RegistrationRequest
    reqs = RegistrationRequest.objects.all()
    pending = reqs.filter(status='pending')
    return render(request, 'registration/registration_requests.html', {
        'requests': reqs,
        'pending_count': pending.count(),
    })


@login_required
@require_permission('manage_registrations')
def registration_approve(request, pk):
    """Registrierungsanfrage genehmigen — erstellt LDAP-User"""
    from authapp.models import RegistrationRequest, EmailTemplate
    from django.utils import timezone
    import secrets

    reg = RegistrationRequest.objects.get(pk=pk)
    if reg.status != 'pending':
        messages.warning(request, 'Diese Anfrage wurde bereits bearbeitet.')
        return redirect('registration_requests')

    if request.method == 'POST':
        try:
            # CN bereinigen: Umlaute ersetzen, Leerzeichen entfernen
            import unicodedata, re
            def _sanitize(s):
                s = s.strip()
                # Umlaute ersetzen
                replacements = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
                                'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'}
                for k, v in replacements.items():
                    s = s.replace(k, v)
                # Akzente entfernen
                s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
                # Nur Buchstaben, Zahlen, Punkt, Bindestrich
                s = re.sub(r'[^a-zA-Z0-9.\-]', '', s)
                return s

            first_clean = _sanitize(reg.first_name)
            last_clean = _sanitize(reg.last_name)
            cn = f"{first_clean}.{last_clean}"
            password = secrets.token_urlsafe(12)

            with LDAPManager() as ldap_conn:
                # Unique CN sicherstellen
                base_cn = cn
                suffix = 1
                while ldap_conn.get_user(cn):
                    suffix += 1
                    cn = f"{base_cn}{suffix}"

                attributes = {
                    'givenName': reg.first_name,
                    'sn': reg.last_name,
                    'cn': cn,
                    'displayName': f"{reg.first_name} {reg.last_name}",
                    'mail': f"{cn}@example-church.de",
                    'userPassword': password,
                }
                ldap_conn.create_user(attributes=attributes)

            # Status aktualisieren
            reg.status = 'approved'
            reg.reviewed_by = request.user
            reg.reviewed_at = timezone.now()
            reg.save()

            # E-Mail an neuen User (HTML)
            try:
                from django.core.mail import EmailMultiAlternatives
                from django.template.loader import render_to_string
                from django.utils.html import strip_tags

                login_url = request.build_absolute_uri('/login/')
                html_message = render_to_string('emails/registration_approved.html', {
                    'first_name': reg.first_name,
                    'username': cn,
                    'password': password,
                    'login_url': login_url,
                })
                plain_message = strip_tags(html_message)

                msg = EmailMultiAlternatives(
                    subject='Willkommen - Ihr Zugang wurde erstellt',
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[reg.email],
                )
                msg.attach_alternative(html_message, 'text/html')
                msg.send(fail_silently=True)
            except Exception:
                pass

            messages.success(request, f'Benutzer {cn} wurde erstellt. Zugangsdaten wurden an {reg.email} gesendet.')
            return redirect('registration_requests')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
        except Exception as e:
            messages.error(request, f'Fehler: {str(e)}')

    return render(request, 'registration/registration_approve.html', {'reg': reg})


@login_required
@require_permission('manage_registrations')
def registration_reject(request, pk):
    """Registrierungsanfrage ablehnen"""
    from authapp.models import RegistrationRequest
    from django.utils import timezone

    reg = RegistrationRequest.objects.get(pk=pk)
    if reg.status != 'pending':
        messages.warning(request, 'Diese Anfrage wurde bereits bearbeitet.')
        return redirect('registration_requests')

    if request.method == 'POST':
        reg.status = 'rejected'
        reg.reviewed_by = request.user
        reg.reviewed_at = timezone.now()
        reg.rejection_reason = request.POST.get('reason', '')
        reg.save()

        # Optional: Mail an Antragsteller (HTML)
        if request.POST.get('send_email'):
            try:
                from django.core.mail import EmailMultiAlternatives
                from django.template.loader import render_to_string
                from django.utils.html import strip_tags

                html_message = render_to_string('emails/registration_rejected.html', {
                    'first_name': reg.first_name,
                    'reason': reg.rejection_reason,
                })
                plain_message = strip_tags(html_message)

                msg = EmailMultiAlternatives(
                    subject='Registrierungsanfrage - Beispielgemeinde',
                    body=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[reg.email],
                )
                msg.attach_alternative(html_message, 'text/html')
                msg.send(fail_silently=True)
            except Exception:
                pass

        messages.success(request, f'Anfrage von {reg.first_name} {reg.last_name} wurde abgelehnt.')
        return redirect('registration_requests')

    return render(request, 'registration/registration_reject.html', {'reg': reg})

@login_required
def profile(request):
    """Profil View - LDAP-Benutzer mit Foto-Upload und Passwortänderung"""
    user_photo_base64 = None
    ldap_user_data = None
    is_ldap_user = False
    user_groups = []

    # Prüfe ob LDAP-Benutzer und hole LDAP-Daten
    try:
        with LDAPManager() as ldap:
            user_data = ldap.get_user(request.user.username)
            if user_data:
                is_ldap_user = True
                attrs = user_data['attributes']

                # Hole alle Attribute
                cn = attrs.get('cn', '')
                if isinstance(cn, list):
                    cn = cn[0] if cn else ''

                given_name = attrs.get('givenName', '')
                if isinstance(given_name, list):
                    given_name = given_name[0] if given_name else ''

                sn = attrs.get('sn', '')
                if isinstance(sn, list):
                    sn = sn[0] if sn else ''

                mail = attrs.get('mail', '')
                if isinstance(mail, list):
                    mail = mail[0] if mail else ''

                title = attrs.get('title', '')
                if isinstance(title, list):
                    title = title[0] if title else ''

                telephone = attrs.get('telephoneNumber', '')
                if isinstance(telephone, list):
                    telephone = telephone[0] if telephone else ''

                mobile = attrs.get('mobile', '')
                if isinstance(mobile, list):
                    mobile = mobile[0] if mobile else ''

                postal_address = attrs.get('postalAddress', '')
                if isinstance(postal_address, list):
                    postal_address = postal_address[0] if postal_address else ''

                birth_date_raw = attrs.get('birthDate', '')
                if isinstance(birth_date_raw, list):
                    birth_date_raw = birth_date_raw[0] if birth_date_raw else ''
                # LDAP-Datum (z.B. "19690324220000Z") in lesbares Format umwandeln
                birth_date_display = ''
                birth_date_iso = ''
                if birth_date_raw:
                    try:
                        from datetime import datetime
                        # Versuche LDAP generalizedTime Format
                        dt = datetime.strptime(str(birth_date_raw)[:8], '%Y%m%d')
                        birth_date_display = dt.strftime('%d.%m.%Y')
                        birth_date_iso = dt.strftime('%Y-%m-%d')
                    except (ValueError, TypeError):
                        birth_date_display = str(birth_date_raw)
                        birth_date_iso = ''

                # Externe mailRoutingAddress-Liste (nicht @example-church.de)
                notification_emails = []
                routing_addrs = attrs.get('mailRoutingAddress', [])
                for addr in routing_addrs:
                    if isinstance(addr, list):
                        addr = addr[0] if addr else ''
                    if isinstance(addr, bytes):
                        addr = addr.decode('utf-8')
                    addr = addr.strip()
                    if addr and not addr.lower().endswith('@example-church.de'):
                        notification_emails.append(addr)
                notification_email = notification_emails[0] if notification_emails else ''

                ldap_user_data = {
                    'cn': cn,
                    'givenName': given_name,
                    'sn': sn,
                    'mail': mail,
                    'notification_email': notification_email,
                    'notification_emails': notification_emails,
                    'title': title,
                    'telephoneNumber': telephone,
                    'mobile': mobile,
                    'postalAddress': postal_address,
                    'birthDate': birth_date_display,
                    'birthDateISO': birth_date_iso,
                    'dn': user_data['dn'],
                }
                user_photo_base64 = ldap.get_photo_as_base64(request.user.username)

                # Hole Gruppenmitgliedschaften
                user_dn = user_data['dn']
                groups = ldap.list_groups()
                for g in groups:
                    g_attrs = g['attributes']
                    g_members = g_attrs.get('member', [])
                    g_cn = g_attrs.get('cn', '')

                    if isinstance(g_cn, list):
                        g_cn = g_cn[0] if g_cn else ''

                    if user_dn in g_members:
                        user_groups.append(g_cn)

    except Exception as e:
        logger.error(f"Fehler beim Laden der LDAP-Daten: {e}")

    # Verarbeite POST-Requests
    if request.method == 'POST':
        # Profildaten ändern
        if 'profile_update' in request.POST and is_ldap_user:
            try:
                update_attrs = {
                    'givenName': request.POST.get('givenName', '').strip(),
                    'sn': request.POST.get('sn', '').strip(),
                }
                update_attrs['displayName'] = f"{update_attrs['givenName']} {update_attrs['sn']}"

                # Optionale Felder
                title = request.POST.get('title', '').strip()
                if title:
                    update_attrs['title'] = title

                telephone = request.POST.get('telephoneNumber', '').strip()
                if telephone:
                    update_attrs['telephoneNumber'] = telephone

                mobile = request.POST.get('mobile', '').strip()
                if mobile:
                    update_attrs['mobile'] = mobile

                postal_address = request.POST.get('postalAddress', '').strip()
                if postal_address:
                    update_attrs['postalAddress'] = postal_address

                birth_date = request.POST.get('birthDate', '').strip()
                if birth_date:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(birth_date, '%Y-%m-%d')
                        update_attrs['birthDate'] = dt.strftime('%Y%m%d000000Z')
                    except ValueError:
                        pass

                with LDAPManager() as ldap_conn:
                    ldap_conn.update_user(request.user.username, update_attrs)

                messages.success(request, 'Ihre Profildaten wurden erfolgreich aktualisiert!')
                return redirect('profile')
            except Exception as e:
                messages.error(request, f'Fehler beim Speichern: {str(e)}')

        # Foto-Upload
        elif 'jpegPhoto' in request.FILES:
            photo_file = request.FILES.get('jpegPhoto')
            if photo_file and is_ldap_user:
                try:
                    with LDAPManager() as ldap:
                        photo_bytes = ldap.process_photo(photo_file)
                        ldap.update_user(request.user.username, {'jpegPhoto': photo_bytes})
                        messages.success(request, 'Ihr Profilfoto wurde erfolgreich aktualisiert!')
                        return redirect('profile')
                except LDAPValidationError as e:
                    messages.error(request, f'Foto-Fehler: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Fehler beim Hochladen des Fotos: {str(e)}')

        # Benachrichtigungs-E-Mails ändern (CRUD-Liste)
        elif 'notification_emails' in request.POST:
            raw = request.POST.get('notification_emails', '').strip()
            if is_ldap_user:
                try:
                    new_external = [a.strip() for a in raw.splitlines() if a.strip()] if raw else []
                    with LDAPManager() as ldap_conn:
                        user_data_fresh = ldap_conn.get_user(request.user.username)
                        if user_data_fresh:
                            attrs = user_data_fresh['attributes']
                            # Interne Adressen behalten
                            internal = []
                            for addr in attrs.get('mailRoutingAddress', []):
                                if isinstance(addr, bytes):
                                    addr = addr.decode('utf-8')
                                addr = addr.strip()
                                if addr and addr.lower().endswith('@example-church.de'):
                                    internal.append(addr)
                            new_addrs = new_external + internal
                            ldap_conn.update_user(request.user.username, {'mailRoutingAddress': new_addrs})
                            messages.success(request, 'Ihre Benachrichtigungs-E-Mails wurden aktualisiert!')
                            return redirect('profile')
                except Exception as e:
                    messages.error(request, f'Fehler beim Ändern der E-Mails: {str(e)}')

        # Passwort-Änderung
        elif 'current_password' in request.POST:
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if new_password != confirm_password:
                messages.error(request, 'Die neuen Passwörter stimmen nicht überein!')
            elif len(new_password) < 8:
                messages.error(request, 'Das Passwort muss mindestens 8 Zeichen lang sein!')
            else:
                try:
                    # Prüfe aktuelles Passwort
                    user = authenticate(username=request.user.username, password=current_password)
                    if user is None:
                        messages.error(request, 'Das aktuelle Passwort ist falsch!')
                    else:
                        # Ändere Passwort in LDAP
                        with LDAPManager() as ldap:
                            ldap.change_password(request.user.username, new_password)
                            messages.success(request, 'Ihr Passwort wurde erfolgreich geändert!')
                            return redirect('profile')
                except Exception as e:
                    messages.error(request, f'Fehler beim Ändern des Passworts: {str(e)}')

    return render(request, 'registration/profile.html', {
        'user_photo_base64': user_photo_base64,
        'ldap_user_data': ldap_user_data,
        'is_ldap_user': is_ldap_user,
        'user_groups': user_groups,
    })


###############################################################################
# FAMILY MANAGEMENT VIEWS
###############################################################################

@login_required
def family_tree(request):
    """
    Familien-Baum Visualisierung
    Zeigt alle Familien mit hierarchischer Struktur (Eltern -> Kinder)
    Benötigt: 'view_members' Berechtigung
    """
    if not has_permission(request.user, 'view_members'):
        messages.error(request, 'Sie haben keine Berechtigung, die Gemeindeliste anzusehen.')
        return redirect('home')
    families = []
    singles = []
    total_members = 0
    largest_family = {'member_count': 0}

    try:
        with LDAPManager() as ldap:
            # Hole alle Root-Benutzer (Top-Level, ohne Parent)
            all_users = ldap.list_users()

            for user in all_users:
                user_dn = user['dn']

                # Ueberspringe nested User (Kinder/Ehepartner)
                if ',cn=' in user_dn:
                    continue

                cn = user['attributes'].get('cn', [b''])[0]
                if isinstance(cn, bytes):
                    cn = cn.decode('utf-8')

                given_name = user['attributes'].get('givenName', [b''])[0]
                sn = user['attributes'].get('sn', [b''])[0]
                mail = user['attributes'].get('mail', [b''])[0]

                if isinstance(given_name, bytes):
                    given_name = given_name.decode('utf-8')
                if isinstance(sn, bytes):
                    sn = sn.decode('utf-8')
                if isinstance(mail, bytes):
                    mail = mail.decode('utf-8')

                # Hole Kinder/Ehepartner dieses Users
                children = ldap.list_users(parent_dn=user_dn)

                family_name = sn or cn
                member_count = len(children) + 1
                total_members += member_count

                if not children:
                    # Einzelmitglied (keine Familie)
                    singles.append({
                        'cn': cn,
                        'name': f"{given_name} {sn}",
                        'email': mail,
                        'photo_base64': ldap.get_photo_as_base64(cn),
                    })
                    continue

                # Baue Kinder-Liste und erkenne Ehepartner
                children_list = []
                spouse = None
                for child in children:
                    child_attrs = child['attributes']
                    child_cn = child_attrs.get('cn', [b''])[0]
                    child_given_name = child_attrs.get('givenName', [b''])[0]
                    child_sn = child_attrs.get('sn', [b''])[0]
                    child_mail = child_attrs.get('mail', [b''])[0]

                    if isinstance(child_cn, bytes):
                        child_cn = child_cn.decode('utf-8')
                    if isinstance(child_given_name, bytes):
                        child_given_name = child_given_name.decode('utf-8')
                    if isinstance(child_sn, bytes):
                        child_sn = child_sn.decode('utf-8')
                    if isinstance(child_mail, bytes):
                        child_mail = child_mail.decode('utf-8')

                    # Ehepartner erkennen via familyRole LDAP-Attribut
                    family_role = child_attrs.get('familyRole', [b''])[0]
                    if isinstance(family_role, bytes):
                        family_role = family_role.decode('utf-8')
                    is_spouse = family_role.lower() == 'spouse'

                    entry = {
                        'cn': child_cn,
                        'name': f"{child_given_name} {child_sn}",
                        'email': child_mail,
                        'is_spouse': is_spouse,
                    }

                    if is_spouse and not spouse:
                        spouse = entry
                    else:
                        children_list.append(entry)

                family = {
                    'head_cn': cn,
                    'name': family_name,
                    'head_name': f"{given_name} {sn}",
                    'head_email': mail,
                    'spouse': spouse,
                    'member_count': member_count,
                    'children': children_list,
                }

                families.append(family)

                # Track groesste Familie
                if member_count > largest_family['member_count']:
                    largest_family = {'name': family_name, 'member_count': member_count}

    except LDAPConnectionError as e:
        logger.error(f"Family-Tree LDAP-Verbindungsfehler: {e}")
        messages.error(request, f"LDAP-Verbindungsfehler: {str(e)}")
    except Exception as e:
        logger.error(f"Family-Tree Fehler: {e}", exc_info=True)
        messages.error(request, f"Fehler beim Laden der Familien: {str(e)}")

    context = {
        'families': sorted(families, key=lambda f: f['name']),
        'singles': sorted(singles, key=lambda s: s['name']),
        'total_members': total_members,
        'total_families': len(families),
        'total_singles': len(singles),
        'largest_family': largest_family,
    }
    return render(request, 'ldap/family_tree.html', context)


@login_required
def family_create(request):
    """
    Neue Familie erstellen (= neuen Familienoberhaupt erstellen)
    Benötigt: 'manage_families' Berechtigung
    """
    if not has_permission(request.user, 'manage_families'):
        messages.error(request, 'Sie haben keine Berechtigung, Familien zu erstellen.')
        return redirect('family_tree')
    if request.method == 'POST':
        try:
            with LDAPManager() as ldap:
                # Hole Formulardaten
                cn = request.POST.get('cn')
                given_name = request.POST.get('givenName')
                sn = request.POST.get('sn')
                mail = request.POST.get('mail', '')
                password = request.POST.get('password')

                # Validierung
                if not all([cn, given_name, sn, password]):
                    messages.error(request, 'Bitte alle Pflichtfelder ausfüllen.')
                    return render(request, 'ldap/family_create.html')

                # Erstelle Benutzer-Attribute
                attributes = {
                    'cn': cn,
                    'givenName': given_name,
                    'sn': sn,
                    'displayName': f"{given_name} {sn}",
                    'mail': mail,
                    'userPassword': password,
                }

                # Erstelle Familienoberhaupt (ohne parent = root level)
                ldap.create_user(attributes, parent_cn=None)

                messages.success(request, f'Familie {sn} erfolgreich erstellt!')
                return redirect('family_tree')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen der Familie: {str(e)}')

    return render(request, 'ldap/family_create.html')


@login_required
def family_add_member(request, parent_cn):
    """
    Kind zu Familie hinzufügen
    Benötigt: 'manage_families' Berechtigung
    """
    if not has_permission(request.user, 'manage_families'):
        messages.error(request, 'Sie haben keine Berechtigung, Familienmitglieder hinzuzufügen.')
        return redirect('family_tree')
    if request.method == 'POST':
        try:
            with LDAPManager() as ldap:
                # Hole Formulardaten
                cn = request.POST.get('cn')
                given_name = request.POST.get('givenName')
                sn = request.POST.get('sn')
                mail = request.POST.get('mail', '')
                password = request.POST.get('password')

                # Validierung
                if not all([cn, given_name, sn, password]):
                    messages.error(request, 'Bitte alle Pflichtfelder ausfüllen.')
                    return render(request, 'ldap/family_add_member.html', {'parent_cn': parent_cn})

                # Erstelle Kind-Attribute
                attributes = {
                    'cn': cn,
                    'givenName': given_name,
                    'sn': sn,
                    'displayName': f"{given_name} {sn}",
                    'mail': mail,
                    'userPassword': password,
                }

                # Optional: Foto hochladen
                photo_file = request.FILES.get('jpegPhoto')
                if photo_file:
                    try:
                        photo_bytes = ldap.process_photo(photo_file)
                        attributes['jpegPhoto'] = photo_bytes
                    except LDAPValidationError as e:
                        messages.error(request, f'Foto-Fehler: {str(e)}')
                        return render(request, 'ldap/family_add_member.html', {'parent_cn': parent_cn})

                # Erstelle Kind unter Parent
                ldap.create_user(attributes, parent_cn=parent_cn)

                messages.success(request, f'Familienmitglied {given_name} {sn} erfolgreich hinzugefügt!')
                return redirect('family_tree')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
        except Exception as e:
            messages.error(request, f'Fehler beim Hinzufügen des Familienmitglieds: {str(e)}')

    # Hole Parent-Informationen für Anzeige
    parent_info = None
    try:
        with LDAPManager() as ldap:
            parent = ldap.get_user(parent_cn)
            if parent:
                given_name = parent['attributes'].get('givenName', [b''])[0]
                sn = parent['attributes'].get('sn', [b''])[0]
                if isinstance(given_name, bytes):
                    given_name = given_name.decode('utf-8')
                if isinstance(sn, bytes):
                    sn = sn.decode('utf-8')
                parent_info = {
                    'cn': parent_cn,
                    'name': f"{given_name} {sn}"
                }
    except:
        pass

    return render(request, 'ldap/family_add_member.html', {
        'parent_cn': parent_cn,
        'parent_info': parent_info
    })


@login_required
def user_edit(request, cn):
    """
    Benutzer bearbeiten
    Benötigt: 'edit_members' Berechtigung
    """
    if not has_permission(request.user, 'edit_members'):
        messages.error(request, 'Sie haben keine Berechtigung, Benutzer zu bearbeiten.')
        return redirect('family_tree')
    ldap_user = None
    is_mail_admin = has_permission(request.user, 'manage_mail') or request.user.is_superuser

    try:
        with LDAPManager() as ldap:
            # Suche User direkt oder als Kind
            user = ldap.get_user(cn)
            if not user:
                # Suche als nested User unter allen Eltern
                all_users = ldap.list_users()
                for u in all_users:
                    u_cn = u['attributes'].get('cn', [''])[0]
                    if isinstance(u_cn, bytes):
                        u_cn = u_cn.decode('utf-8')
                    if u_cn == cn:
                        user = u
                        break
            if not user:
                messages.error(request, 'Benutzer nicht gefunden.')
                return redirect('family_tree')

            # Dekodiere Attribute
            attributes = user['attributes']
            def _decode_attr(attrs, name, default=''):
                val = attrs.get(name, [b''])[0]
                return val.decode('utf-8') if isinstance(val, bytes) else (val or default)

            def _decode_attr_list(attrs, name):
                """Dekodiert multi-value LDAP-Attribute als Liste"""
                values = attrs.get(name, [])
                result = []
                for val in values:
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    val = val.strip()
                    if val:
                        result.append(val)
                return result

            ldap_user = {
                'cn': cn,
                'givenName': _decode_attr(attributes, 'givenName'),
                'sn': _decode_attr(attributes, 'sn'),
                'mail': _decode_attr(attributes, 'mail'),
                'mail_list': _decode_attr_list(attributes, 'mail'),
                'mailRoutingAddress': _decode_attr(attributes, 'mailRoutingAddress'),
                'mailRoutingAddress_list': _decode_attr_list(attributes, 'mailRoutingAddress'),
                'mailAliasAddress_list': _decode_attr_list(attributes, 'mailAliasAddress'),
                'mailAliasEnabled': _decode_attr(attributes, 'mailAliasEnabled'),
                'mailRoutingEnabled': _decode_attr(attributes, 'mailRoutingEnabled'),
                'mailQuota': _decode_attr(attributes, 'mailQuota'),
                'displayName': _decode_attr(attributes, 'displayName'),
                'photo_base64': ldap.get_photo_as_base64(cn),
            }

            # Geburtsdatum aus LDAP-Format parsen
            birth_date_raw = _decode_attr(attributes, 'birthDate')
            if birth_date_raw:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(str(birth_date_raw)[:8], '%Y%m%d')
                    ldap_user['birthDate'] = dt.strftime('%d.%m.%Y')
                    ldap_user['birthDateISO'] = dt.strftime('%Y-%m-%d')
                except (ValueError, TypeError):
                    ldap_user['birthDate'] = birth_date_raw
                    ldap_user['birthDateISO'] = ''
            else:
                ldap_user['birthDate'] = ''
                ldap_user['birthDateISO'] = ''

            # is_mail_admin bereits oben gesetzt

            if request.method == 'POST':
                # Update Attribute
                new_attributes = {
                    'givenName': request.POST.get('givenName'),
                    'sn': request.POST.get('sn'),
                    'displayName': f"{request.POST.get('givenName')} {request.POST.get('sn')}",
                }

                # Private E-Mail (mailRoutingAddress) - editierbar
                private_mail = request.POST.get('mailRoutingAddress', '')
                if private_mail:
                    new_attributes['mailRoutingAddress'] = private_mail

                # Admin-Mail-Attribute (nur mit manage_mail Berechtigung)
                if has_permission(request.user, 'manage_mail') or request.user.is_superuser:
                    # Multi-value Felder: Zeilenweise getrennt
                    mail_values = request.POST.get('mail_list', '').strip()
                    if mail_values:
                        new_attributes['mail'] = [v.strip() for v in mail_values.splitlines() if v.strip()]

                    routing_values = request.POST.get('mailRoutingAddress_list', '').strip()
                    if routing_values:
                        new_attributes['mailRoutingAddress'] = [v.strip() for v in routing_values.splitlines() if v.strip()]

                    alias_values = request.POST.get('mailAliasAddress_list', '').strip()
                    if alias_values:
                        new_attributes['mailAliasAddress'] = [v.strip() for v in alias_values.splitlines() if v.strip()]

                    # Mail-Flags nur setzen wenn User mailExtension hat
                    user_oc = attributes.get('objectClass', [])
                    user_oc_str = [o.decode('utf-8') if isinstance(o, bytes) else o for o in user_oc]
                    if 'mailExtension' in user_oc_str:
                        new_attributes['mailAliasEnabled'] = 'TRUE' if request.POST.get('mailAliasEnabled') else 'FALSE'
                        new_attributes['mailRoutingEnabled'] = 'TRUE' if request.POST.get('mailRoutingEnabled') else 'FALSE'

                        mail_quota = request.POST.get('mailQuota', '').strip()
                        if mail_quota:
                            new_attributes['mailQuota'] = mail_quota

                # Optional: Weitere Felder
                title = request.POST.get('title', '')
                if title:
                    new_attributes['title'] = title

                telephone = request.POST.get('telephoneNumber', '')
                if telephone:
                    new_attributes['telephoneNumber'] = telephone

                mobile = request.POST.get('mobile', '')
                if mobile:
                    new_attributes['mobile'] = mobile

                postal_address = request.POST.get('postalAddress', '')
                if postal_address:
                    new_attributes['postalAddress'] = postal_address

                birth_date = request.POST.get('birthDate', '')
                if birth_date:
                    # ISO-Datum (YYYY-MM-DD) ins LDAP generalizedTime-Format konvertieren
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(birth_date, '%Y-%m-%d')
                        new_attributes['birthDate'] = dt.strftime('%Y%m%d000000Z')
                    except ValueError:
                        new_attributes['birthDate'] = birth_date

                # Familienrolle
                family_role = request.POST.get('familyRole', '').strip()
                if family_role:
                    new_attributes['familyRole'] = family_role

                # Status (Gruppenmitgliedschaft aendern)
                new_status = request.POST.get('status', '').strip()
                if new_status:
                    status_group_map = {
                        'Mitglied': 'Mitglieder',
                        'Besucher': 'Besucher',
                        'Gast': 'Gäste',
                    }
                    # Aus allen Status-Gruppen entfernen
                    user_dn_full = user['dn']
                    for group_cn in status_group_map.values():
                        try:
                            group_dn = f"cn={group_cn},ou=Groups,dc=example-church,dc=de"
                            group_data = ldap.get_group(group_dn)
                            if group_data:
                                members = group_data['attributes'].get('member', [])
                                if user_dn_full in members:
                                    ldap.remove_member(group_dn, user_dn_full)
                        except Exception:
                            pass
                    # In die neue Status-Gruppe hinzufuegen
                    target_group = status_group_map.get(new_status)
                    if target_group:
                        try:
                            group_dn = f"cn={target_group},ou=Groups,dc=example-church,dc=de"
                            ldap.add_member(group_dn, user_dn_full)
                        except Exception as e:
                            logger.warning(f"Konnte {cn} nicht zu Gruppe {target_group} hinzufuegen: {e}")

                # Account deaktivieren/aktivieren
                # Nur setzen wenn das Schema-Attribut existiert (User hat postModernalPerson)
                oc = attributes.get('objectClass', [])
                oc_list = [o.decode('utf-8') if isinstance(o, bytes) else o for o in oc]
                if 'postModernalPerson' in oc_list:
                    new_attributes['accountDisabled'] = 'TRUE' if request.POST.get('accountDisabled') else 'FALSE'

                # Optional: Passwort ändern mit Validierung
                new_password = request.POST.get('password')
                new_password2 = request.POST.get('password2')
                if new_password or new_password2:
                    if new_password != new_password2:
                        messages.error(request, 'Die beiden Passwörter stimmen nicht überein.')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from django.http import JsonResponse
                            return JsonResponse({'success': False, 'error': 'Passwörter stimmen nicht überein'}, status=400)
                        return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user, 'is_mail_admin': is_mail_admin})
                    if len(new_password) < 8:
                        messages.error(request, 'Das Passwort muss mindestens 8 Zeichen lang sein.')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from django.http import JsonResponse
                            return JsonResponse({'success': False, 'error': 'Passwort zu kurz'}, status=400)
                        return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user, 'is_mail_admin': is_mail_admin})
                    new_attributes['userPassword'] = new_password

                # Optional: Foto hochladen
                photo_file = request.FILES.get('jpegPhoto')
                if photo_file:
                    try:
                        photo_bytes = ldap.process_photo(photo_file)
                        new_attributes['jpegPhoto'] = photo_bytes
                    except LDAPValidationError as e:
                        messages.error(request, f'Foto-Fehler: {str(e)}')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from django.http import JsonResponse
                            return JsonResponse({'success': False, 'error': str(e)}, status=400)
                        return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user, 'is_mail_admin': is_mail_admin})

                # Parent-CN aus DN extrahieren
                user_dn = user['dn']
                old_parent_cn = None
                if ',cn=' in user_dn:
                    parts = user_dn.split(',')
                    if len(parts) >= 2 and parts[1].startswith('cn='):
                        old_parent_cn = parts[1][3:]

                new_parent_cn = request.POST.get('parent_cn', '').strip() or None

                # Heirats-Logik: familyRole=spouse + parent_cn gesetzt
                # => automatisch zum Partner verschieben
                if family_role == 'spouse' and new_parent_cn and new_parent_cn != old_parent_cn:
                    # Nachname ändert sich vermutlich bei Heirat
                    new_sn = new_attributes.get('sn', '')
                    new_given = new_attributes.get('givenName', '')
                    old_sn = user['attributes'].get('sn', [''])[0]
                    if isinstance(old_sn, bytes):
                        old_sn = old_sn.decode('utf-8')

                    # Neuen CN generieren wenn Nachname sich geaendert hat
                    new_cn = f"{new_given}.{new_sn}" if new_sn != old_sn else cn

                    # Attribute updaten (noch am alten Ort)
                    ldap.update_user(cn, new_attributes, parent_cn=old_parent_cn)

                    # User zum Partner verschieben
                    ldap.move_user(cn, old_parent_cn=old_parent_cn, new_parent_cn=new_parent_cn)

                    # CN umbenennen wenn Nachname geaendert
                    if new_cn != cn:
                        old_dn_after_move = ldap.build_dn(cn, ldap.build_dn(new_parent_cn))
                        new_rdn = f"cn={new_cn}"
                        ldap.conn.rename_s(old_dn_after_move, new_rdn)
                        # Auch uid, homeDirectory, mail etc. anpassen
                        update_after_rename = {
                            'uid': new_cn,
                            'homeDirectory': f'/home/example-church.de/{new_cn}',
                            'displayName': f"{new_given} {new_sn}",
                        }
                        ldap.update_user(new_cn, update_after_rename, parent_cn=new_parent_cn)
                        messages.success(request, f'{new_given} {old_sn} hat geheiratet und heisst jetzt {new_given} {new_sn}! Verschoben zu Familie {new_parent_cn}.')
                    else:
                        messages.success(request, f'{new_given} wurde als Ehepartner zu {new_parent_cn} verschoben!')

                elif new_parent_cn != old_parent_cn:
                    # Normales Verschieben (kein Heirat)
                    ldap.update_user(cn, new_attributes, parent_cn=old_parent_cn)
                    ldap.move_user(cn, old_parent_cn=old_parent_cn, new_parent_cn=new_parent_cn)
                    messages.success(request, f'Benutzer aktualisiert und {"zu " + new_parent_cn + " verschoben" if new_parent_cn else "auf Top-Level verschoben"}!')
                else:
                    ldap.update_user(cn, new_attributes, parent_cn=old_parent_cn)
                    messages.success(request, 'Benutzer erfolgreich aktualisiert!')

                # Bei AJAX-Request JSON zurückgeben
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'success': True, 'message': 'Benutzer erfolgreich aktualisiert!'})

                return redirect('family_tree')

    except LDAPOperationError as e:
        messages.error(request, f'LDAP-Fehler: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        messages.error(request, f'Fehler beim Bearbeiten: {str(e)}')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user, 'is_mail_admin': is_mail_admin})


@login_required
@user_passes_test(is_ldap_admin)
def user_create(request):
    """
    Neuen Benutzer erstellen
    Benötigt: 'edit_members' Berechtigung
    """
    if not has_permission(request.user, 'edit_members'):
        messages.error(request, 'Sie haben keine Berechtigung, Benutzer zu erstellen.')
        return redirect('family_tree')

    if request.method == 'POST':
        try:
            with LDAPManager() as ldap:
                # Hole Basis-Daten
                given_name = request.POST.get('givenName')
                sn = request.POST.get('sn')
                mail = request.POST.get('mail', '')
                password = request.POST.get('password')
                password2 = request.POST.get('password2')
                parent_cn = request.POST.get('parent_cn', '')

                # Validierung
                if not given_name or not sn:
                    messages.error(request, 'Vorname und Nachname sind erforderlich.')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({'success': False, 'error': 'Vorname und Nachname erforderlich'}, status=400)
                    return redirect('ldap_user_search')

                if not password or not password2:
                    messages.error(request, 'Passwort ist erforderlich.')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({'success': False, 'error': 'Passwort erforderlich'}, status=400)
                    return redirect('ldap_user_search')

                if password != password2:
                    messages.error(request, 'Die beiden Passwörter stimmen nicht überein.')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({'success': False, 'error': 'Passwörter stimmen nicht überein'}, status=400)
                    return redirect('ldap_user_search')

                if len(password) < 8:
                    messages.error(request, 'Das Passwort muss mindestens 8 Zeichen lang sein.')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({'success': False, 'error': 'Passwort zu kurz'}, status=400)
                    return redirect('ldap_user_search')

                # Generiere CN (Benutzername)
                cn = f"{given_name}.{sn}"

                # Prüfe ob CN bereits existiert
                existing_user = ldap.get_user(cn, parent_cn=parent_cn if parent_cn else None)
                if existing_user:
                    messages.error(request, f'Benutzer {cn} existiert bereits.')
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse({'success': False, 'error': f'Benutzer {cn} existiert bereits'}, status=400)
                    return redirect('ldap_user_search')

                # Erstelle Attribut-Dict
                attributes = {
                    'givenName': given_name,
                    'sn': sn,
                    'cn': cn,
                    'displayName': f"{given_name} {sn}",
                    'userPassword': password,
                }

                if mail:
                    attributes['mail'] = mail

                # Optional: Weitere Felder
                title = request.POST.get('title', '')
                if title:
                    attributes['title'] = title

                telephone = request.POST.get('telephoneNumber', '')
                if telephone:
                    attributes['telephoneNumber'] = telephone

                mobile = request.POST.get('mobile', '')
                if mobile:
                    attributes['mobile'] = mobile

                postal_address = request.POST.get('postalAddress', '')
                if postal_address:
                    attributes['postalAddress'] = postal_address

                birth_date = request.POST.get('birthDate', '')
                if birth_date:
                    attributes['birthDate'] = birth_date

                # Optional: Foto hochladen
                photo_file = request.FILES.get('jpegPhoto')
                if photo_file:
                    try:
                        photo_bytes = ldap.process_photo(photo_file)
                        attributes['jpegPhoto'] = photo_bytes
                    except LDAPValidationError as e:
                        messages.error(request, f'Foto-Fehler: {str(e)}')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from django.http import JsonResponse
                            return JsonResponse({'success': False, 'error': str(e)}, status=400)
                        return redirect('ldap_user_search')

                # Erstelle Benutzer
                ldap.create_user(
                    attributes=attributes,
                    parent_cn=parent_cn if parent_cn else None
                )

                messages.success(request, f'Benutzer {cn} erfolgreich erstellt!')

                # Bei AJAX-Request JSON zurückgeben
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    from django.http import JsonResponse
                    return JsonResponse({'success': True, 'message': f'Benutzer {cn} erfolgreich erstellt!'})

                return redirect('ldap_user_search')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            messages.error(request, f'Fehler beim Erstellen: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return redirect('ldap_user_search')


@login_required
@require_permission('edit_members')
@require_http_methods(["POST"])
def user_delete(request, cn):
    """
    Benutzer aus LDAP löschen
    Benötigt: 'edit_members' Berechtigung
    Sendet Warn-E-Mail an den Benutzer
    """
    try:
        with LDAPManager() as ldap_mgr:
            # Hole Benutzerdaten vor dem Löschen
            user_data = ldap_mgr.get_user(cn)
            if not user_data:
                messages.error(request, f'Benutzer {cn} nicht gefunden.')
                return redirect('ldap_user_search')

            attrs = user_data['attributes']
            given_name = attrs.get('givenName', [''])[0] if isinstance(attrs.get('givenName', ['']), list) else attrs.get('givenName', '')
            sn = attrs.get('sn', [''])[0] if isinstance(attrs.get('sn', ['']), list) else attrs.get('sn', '')
            user_dn = user_data['dn']

            # Sammle alle E-Mail-Adressen für Benachrichtigung
            mail_addresses = []
            for attr_name in ['mailRoutingAddress', 'mail']:
                val = attrs.get(attr_name, [])
                if isinstance(val, list):
                    mail_addresses.extend(val)
                elif val:
                    mail_addresses.append(val)

            # Filtere externe Adressen (nicht @example-church.de)
            external_emails = [m for m in mail_addresses if m and '@example-church.de' not in m]

            # Prüfe ob Benutzer Kinder hat
            children = ldap_mgr.list_users(parent_dn=user_dn)
            force = len(children) > 0

            if force:
                # Bestätigung erforderlich für Familienlöschung
                confirm = request.POST.get('confirm_family_delete')
                if confirm != 'yes':
                    messages.warning(request,
                        f'Benutzer {cn} hat {len(children)} Kind(er). '
                        f'Bitte bestätigen Sie die Löschung der gesamten Familie.')
                    return redirect('ldap_user_search')

            # Lösche aus LDAP
            ldap_mgr.delete_user(cn, force=force)

            # Lösche auch den Django-User falls vorhanden
            from django.contrib.auth.models import User
            django_user = User.objects.filter(username__iexact=cn).first()
            if django_user:
                django_user.delete()

            # Log
            LDAPUserLog.objects.create(
                user=request.user,
                action='delete_user',
                details=f'Benutzer {cn} ({given_name} {sn}) gelöscht',
                ip_address=request.META.get('REMOTE_ADDR')
            )

            # Warn-E-Mail an den gelöschten Benutzer senden
            if external_emails:
                try:
                    from django.core.mail import EmailMultiAlternatives
                    from django.template.loader import render_to_string
                    from django.utils.html import strip_tags

                    html_message = render_to_string('emails/account_deleted.html', {
                        'first_name': given_name,
                        'last_name': sn,
                        'username': cn,
                        'deleted_by': request.user.get_full_name() or request.user.username,
                    })
                    plain_message = strip_tags(html_message)

                    msg = EmailMultiAlternatives(
                        subject='Ihr Zugang wurde entfernt - Beispielgemeinde',
                        body=plain_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=external_emails,
                    )
                    msg.attach_alternative(html_message, 'text/html')
                    msg.send(fail_silently=True)
                    logger.info(f"Lösch-Benachrichtigung gesendet an {external_emails} für {cn}")
                except Exception as mail_err:
                    logger.error(f"Fehler beim Senden der Lösch-Benachrichtigung: {mail_err}")

            if force:
                messages.success(request, f'Benutzer {cn} und {len(children)} Kind(er) erfolgreich gelöscht.')
            else:
                messages.success(request, f'Benutzer {cn} erfolgreich gelöscht.')

    except LDAPOperationError as e:
        messages.error(request, f'LDAP-Fehler beim Löschen: {str(e)}')
    except Exception as e:
        logger.error(f"Fehler beim Löschen von {cn}: {e}")
        messages.error(request, f'Fehler beim Löschen: {str(e)}')

    return redirect('ldap_user_search')


###############################################################################
# GROUP MANAGEMENT VIEWS
###############################################################################

@login_required
@user_passes_test(is_ldap_admin)
def group_list(request):
    """
    Gruppenverwaltung - Liste aller Gruppen mit hierarchischer Struktur
    """
    groups = []
    search_query = request.GET.get('q', '')

    try:
        with LDAPManager() as ldap_mgr:
            # Hole alle Gruppen
            all_groups = ldap_mgr.list_groups()

            # Parse alle Gruppen
            all_group_data = []

            for group in all_groups:
                dn = group['dn']
                attrs = group['attributes']

                # Dekodiere DN falls bytes
                if isinstance(dn, bytes):
                    dn = dn.decode('utf-8')

                # Hole Attribute (LDAPManager dekodiert bereits zu Strings/Listen)
                cn = attrs.get('cn', '')
                description = attrs.get('description', '')
                members = attrs.get('member', [])

                # cn und description können String oder Liste sein
                if isinstance(cn, list):
                    cn = cn[0] if cn else ''
                if isinstance(description, list):
                    description = description[0] if description else ''

                # Zähle Mitglieder (ohne 'cn=nobody')
                # members ist jetzt eine Liste von Strings (nicht Bytes)
                member_count = len([m for m in members if 'cn=nobody' not in str(m)])

                # Bestimme ob nested (hat ,cn= vor ,ou=)
                is_nested = ',cn=' in dn and dn.index(',cn=') < dn.index(',ou=')

                # Extrahiere Parent-Gruppe falls nested
                parent_cn = None
                level = 0
                if is_nested:
                    parts = dn.split(',')
                    # Zähle wie viele cn= es gibt vor dem ou=
                    level = len([p for p in parts if p.startswith('cn=')]) - 1

                    # Parent ist die erste cn= nach der aktuellen Gruppe
                    # DN Format: cn=child,cn=parent,ou=Groups,...
                    # parts[0] = cn=child
                    # parts[1] = cn=parent
                    if len(parts) > 1 and parts[1].startswith('cn='):
                        parent_cn = parts[1][3:]  # Entferne 'cn='

                group_data = {
                    'dn': dn,
                    'cn': cn,
                    'description': description,
                    'member_count': member_count,
                    'is_nested': is_nested,
                    'parent_cn': parent_cn,
                    'level': level,
                }

                # Filter nach Suchbegriff
                if search_query:
                    search_lower = search_query.lower()
                    match = (
                        search_lower in cn.lower() or
                        search_lower in description.lower()
                    )
                    if match:
                        all_group_data.append(group_data)
                else:
                    all_group_data.append(group_data)

            # Sortiere hierarchisch: Top-Level-Gruppen alphabetisch,
            # verschachtelte Gruppen direkt unter ihren Parents
            def build_hierarchy(groups_list):
                """Baut hierarchische Liste auf"""
                result = []

                # Erstelle Map: cn -> group_data
                groups_by_cn = {g['cn']: g for g in groups_list}

                # Hole alle Top-Level Gruppen (sortiert)
                top_level = sorted(
                    [g for g in groups_list if not g['is_nested']],
                    key=lambda x: x['cn']
                )

                # Rekursive Funktion zum Hinzufügen von Kindern
                def add_with_children(group):
                    result.append(group)
                    # Finde alle Kinder dieser Gruppe
                    children = sorted(
                        [g for g in groups_list if g['parent_cn'] == group['cn']],
                        key=lambda x: x['cn']
                    )
                    for child in children:
                        add_with_children(child)

                # Füge jede Top-Level-Gruppe mit ihren Kindern hinzu
                for top_group in top_level:
                    add_with_children(top_group)

                return result

            groups = build_hierarchy(all_group_data)

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP Verbindungsfehler: {str(e)}")
    except Exception as e:
        messages.error(request, f"LDAP Suchfehler: {str(e)}")

    # Pagination mit waehlbarer Seitengroesse
    from django.core.paginator import Paginator
    per_page_options = [10, 20, 50, 100]
    try:
        per_page = int(request.GET.get('per_page', 50))
        if per_page not in per_page_options:
            per_page = 50
    except (ValueError, TypeError):
        per_page = 50
    paginator = Paginator(groups, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'ldap/group_list.html', {
        'groups': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
        'per_page_options': per_page_options,
        'search_query': search_query,
    })


@login_required
@user_passes_test(is_ldap_admin)
def group_detail(request, group_cn):
    """
    Gruppendetails mit Mitgliederverwaltung
    """
    group_info = None
    members = []
    all_users = []

    try:
        with LDAPManager() as ldap_mgr:
            # Hole Gruppen-Details
            groups = ldap_mgr.list_groups()
            for group in groups:
                attrs = group['attributes']
                cn = attrs.get('cn', '')
                if isinstance(cn, list):
                    cn = cn[0] if cn else ''

                if cn == group_cn:
                    description = attrs.get('description', '')
                    if isinstance(description, list):
                        description = description[0] if description else ''

                    members_dn = attrs.get('member', [])
                    if not isinstance(members_dn, list):
                        members_dn = [members_dn] if members_dn else []

                    group_info = {
                        'dn': group['dn'],
                        'cn': cn,
                        'description': description,
                        'members_dn': members_dn,
                    }
                    break

            if not group_info:
                messages.error(request, f'Gruppe {group_cn} nicht gefunden')
                return redirect('group_list')

            # Hole alle Benutzer für Dropdown
            all_ldap_users = ldap_mgr.list_users()
            for user in all_ldap_users:
                attrs = user['attributes']
                cn = attrs.get('cn', '')
                given_name = attrs.get('givenName', '')
                sn = attrs.get('sn', '')

                if isinstance(cn, list):
                    cn = cn[0] if cn else ''
                if isinstance(given_name, list):
                    given_name = given_name[0] if given_name else ''
                if isinstance(sn, list):
                    sn = sn[0] if sn else ''

                all_users.append({
                    'dn': user['dn'],
                    'cn': cn,
                    'givenName': given_name,
                    'sn': sn,
                    'displayName': f"{given_name} {sn}",
                })

            # Parse Mitglieder-DNs zu User-Infos
            for member_dn in group_info['members_dn']:
                # Ignoriere cn=nobody
                if 'cn=nobody' in str(member_dn):
                    continue

                # Finde User in all_users
                for user in all_users:
                    if user['dn'] == member_dn:
                        members.append(user)
                        break

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP Verbindungsfehler: {str(e)}")
        return redirect('group_list')
    except Exception as e:
        messages.error(request, f"LDAP Fehler: {str(e)}")
        return redirect('group_list')

    return render(request, 'ldap/group_detail.html', {
        'group': group_info,
        'members': members,
        'all_users': all_users,
    })


@login_required
@user_passes_test(is_ldap_admin)
def group_add_member(request, group_cn):
    """
    Mitglied zu Gruppe hinzufügen
    """
    if request.method == 'POST':
        user_dn = request.POST.get('user_dn')

        if not user_dn:
            messages.error(request, 'Kein Benutzer ausgewählt')
            return redirect('group_detail', group_cn=group_cn)

        try:
            with LDAPManager() as ldap_mgr:
                # Hole Gruppen-DN
                groups = ldap_mgr.list_groups()
                group_dn = None
                for group in groups:
                    attrs = group['attributes']
                    cn = attrs.get('cn', '')
                    if isinstance(cn, list):
                        cn = cn[0] if cn else ''
                    if cn == group_cn:
                        group_dn = group['dn']
                        break

                if not group_dn:
                    messages.error(request, f'Gruppe {group_cn} nicht gefunden')
                    return redirect('group_list')

                # Füge Mitglied hinzu
                ldap_mgr.add_member(group_dn, user_dn)
                messages.success(request, f'Benutzer erfolgreich zur Gruppe hinzugefügt')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
        except Exception as e:
            messages.error(request, f'Fehler: {str(e)}')

    return redirect('group_detail', group_cn=group_cn)


@login_required
@user_passes_test(is_ldap_admin)
def group_remove_member(request, group_cn):
    """
    Mitglied aus Gruppe entfernen
    """
    if request.method == 'POST':
        user_dn = request.POST.get('user_dn')

        if not user_dn:
            messages.error(request, 'Kein Benutzer ausgewählt')
            return redirect('group_detail', group_cn=group_cn)

        try:
            with LDAPManager() as ldap_mgr:
                # Hole Gruppen-DN
                groups = ldap_mgr.list_groups()
                group_dn = None
                for group in groups:
                    attrs = group['attributes']
                    cn = attrs.get('cn', '')
                    if isinstance(cn, list):
                        cn = cn[0] if cn else ''
                    if cn == group_cn:
                        group_dn = group['dn']
                        break

                if not group_dn:
                    messages.error(request, f'Gruppe {group_cn} nicht gefunden')
                    return redirect('group_list')

                # Entferne Mitglied
                ldap_mgr.remove_member(group_dn, user_dn)
                messages.success(request, f'Benutzer erfolgreich aus Gruppe entfernt')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
        except Exception as e:
            messages.error(request, f'Fehler: {str(e)}')

    return redirect('group_detail', group_cn=group_cn)


###############################################################################
# MEMBER MANAGEMENT - Neues Mitglied aufnehmen
###############################################################################

@login_required
@user_passes_test(is_ldap_admin)
def member_add(request):
    """
    Neues Mitglied aufnehmen - Person zur Gruppe 'Mitglieder' hinzufügen
    Zeigt Besucher und Gäste die noch nicht Mitglieder sind
    """
    non_members = []  # Benutzer die noch nicht in "Mitglieder" sind
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')  # Filter: Besucher, Gäste, Mitglieder

    try:
        with LDAPManager() as ldap_mgr:
            # Hole Gruppe "Mitglieder"
            groups = ldap_mgr.list_groups()
            mitglieder_group = None
            mitglieder_members = []

            for group in groups:
                attrs = group['attributes']
                cn = attrs.get('cn', '')
                if isinstance(cn, list):
                    cn = cn[0] if cn else ''

                if cn == 'Mitglieder':
                    mitglieder_group = group
                    members_dn = attrs.get('member', [])
                    if not isinstance(members_dn, list):
                        members_dn = [members_dn] if members_dn else []
                    mitglieder_members = members_dn
                    break

            if not mitglieder_group:
                messages.error(request, 'Gruppe "Mitglieder" nicht gefunden')
                return redirect('ldap_admin')

            # Hole alle Benutzer
            all_users = ldap_mgr.list_users()

            # Filtere Benutzer die NICHT in "Mitglieder" sind
            for user in all_users:
                user_dn = user['dn']

                # Überspringe wenn bereits Mitglied
                if user_dn in mitglieder_members or 'cn=nobody' in str(user_dn):
                    continue

                attrs = user['attributes']
                cn = attrs.get('cn', '')
                given_name = attrs.get('givenName', '')
                sn = attrs.get('sn', '')
                mail = attrs.get('mail', '')

                # Handle Listen
                if isinstance(cn, list):
                    cn = cn[0] if cn else ''
                if isinstance(given_name, list):
                    given_name = given_name[0] if given_name else ''
                if isinstance(sn, list):
                    sn = sn[0] if sn else ''
                if isinstance(mail, list):
                    mail = mail[0] if mail else ''

                # Bestimme aktuellen Status (aus anderen Gruppen)
                status = 'Nicht zugeordnet'
                for g in groups:
                    g_attrs = g['attributes']
                    g_cn = g_attrs.get('cn', '')
                    if isinstance(g_cn, list):
                        g_cn = g_cn[0] if g_cn else ''

                    g_members = g_attrs.get('member', [])
                    if not isinstance(g_members, list):
                        g_members = [g_members] if g_members else []

                    if user_dn in g_members:
                        if g_cn == 'Besucher':
                            status = 'Besucher'
                            break
                        elif g_cn == 'Gäste':
                            status = 'Gast'
                            break
                        elif g_cn == 'Angehörige':
                            status = 'Angehöriger'
                            break
                        elif g_cn == 'Ehepartner':
                            status = 'Ehepartner'
                            break

                # Status-Filter anwenden
                if status_filter:
                    if status_filter == 'Besucher' and status != 'Besucher':
                        continue
                    elif status_filter == 'Gäste' and status != 'Gast':
                        continue
                    elif status_filter == 'Ehepartner' and status != 'Ehepartner':
                        continue

                # Suchfilter anwenden
                if search_query:
                    search_lower = search_query.lower()
                    match = (
                        search_lower in cn.lower() or
                        search_lower in given_name.lower() or
                        search_lower in sn.lower() or
                        search_lower in mail.lower() or
                        search_lower in status.lower() or
                        search_lower in f"{given_name} {sn}".lower()
                    )
                    if not match:
                        continue

                non_members.append({
                    'dn': user_dn,
                    'cn': cn,
                    'givenName': given_name,
                    'sn': sn,
                    'mail': mail,
                    'displayName': f"{given_name} {sn}",
                    'status': status,
                })

            # Sortiere nach Name
            non_members.sort(key=lambda x: x['displayName'])

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP Verbindungsfehler: {str(e)}")
        return redirect('ldap_admin')
    except Exception as e:
        messages.error(request, f"LDAP Fehler: {str(e)}")
        return redirect('ldap_admin')

    return render(request, 'ldap/member_add.html', {
        'non_members': non_members,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@login_required
@user_passes_test(is_ldap_admin)
def member_add_existing(request):
    """
    Bestehenden Benutzer zur Gruppe 'Mitglieder' hinzufügen
    """
    if request.method == 'POST':
        user_dn = request.POST.get('user_dn')

        if not user_dn:
            messages.error(request, 'Kein Benutzer ausgewählt')
            return redirect('member_add')

        try:
            with LDAPManager() as ldap_mgr:
                # Hole Gruppe "Mitglieder"
                groups = ldap_mgr.list_groups()
                mitglieder_dn = None

                for group in groups:
                    attrs = group['attributes']
                    cn = attrs.get('cn', '')
                    if isinstance(cn, list):
                        cn = cn[0] if cn else ''

                    if cn == 'Mitglieder':
                        mitglieder_dn = group['dn']
                        break

                if not mitglieder_dn:
                    messages.error(request, 'Gruppe "Mitglieder" nicht gefunden')
                    return redirect('member_add')

                # Füge zur Gruppe hinzu
                ldap_mgr.add_member(mitglieder_dn, user_dn)
                messages.success(request, 'Person erfolgreich als Mitglied aufgenommen')

                # Sende Begrüßungs-E-Mail
                try:
                    from authapp.models import EmailTemplate
                    from django.core.mail import send_mail
                    from django.conf import settings

                    # Hole die aktive Begrüßungs-Vorlage
                    template = EmailTemplate.objects.filter(
                        template_type='member_welcome',
                        is_active=True
                    ).first()

                    if template and template.send_automatically:
                        # Hole Benutzerdaten aus LDAP
                        user_data = ldap_mgr.get_user(user_dn)
                        if user_data:
                            attrs = user_data.get('attributes', {})

                            # Extrahiere E-Mail
                            email = attrs.get('mail', [])
                            if isinstance(email, list):
                                email = email[0] if email else None

                            if email:
                                # Extrahiere weitere Daten
                                cn = attrs.get('cn', [''])[0] if isinstance(attrs.get('cn'), list) else attrs.get('cn', '')
                                given_name = attrs.get('givenName', [''])[0] if isinstance(attrs.get('givenName'), list) else attrs.get('givenName', '')
                                sn = attrs.get('sn', [''])[0] if isinstance(attrs.get('sn'), list) else attrs.get('sn', '')

                                # Prepare template context
                                context = {
                                    'username': cn,
                                    'email': email,
                                    'first_name': given_name,
                                    'last_name': sn,
                                    'name': f"{given_name} {sn}".strip() or cn
                                }

                                # Render template
                                subject, body = template.render(context)

                                # Send email
                                send_mail(
                                    subject=subject,
                                    message=body,
                                    from_email=settings.DEFAULT_FROM_EMAIL,
                                    recipient_list=[email],
                                    fail_silently=False
                                )

                                messages.success(request, f'Begrüßungs-E-Mail wurde an {email} gesendet')
                            else:
                                messages.warning(request, 'Keine E-Mail-Adresse für Begrüßung gefunden')

                except Exception as email_error:
                    # Log the error but don't fail the whole operation
                    messages.warning(request, f'Mitglied wurde hinzugefügt, aber E-Mail konnte nicht gesendet werden: {str(email_error)}')

        except LDAPOperationError as e:
            messages.error(request, f'LDAP-Fehler: {str(e)}')
        except Exception as e:
            messages.error(request, f'Fehler: {str(e)}')

    return redirect('member_add')


# ==================== BACKUP VIEWS ====================

@login_required
@user_passes_test(is_ldap_admin)
def backup_dashboard(request):
    """
    Backup-Dashboard mit Historie und Steuerung
    """
    from .models import LDAPBackup
    from django.core.management import call_command
    from io import StringIO

    # Hole alle Backups (neueste zuerst)
    backups = LDAPBackup.objects.all().order_by('-created_at')

    # Statistiken
    stats = {
        'total_backups': backups.count(),
        'completed': backups.filter(status='completed').count(),
        'failed': backups.filter(status='failed').count(),
        'running': backups.filter(status='running').count(),
    }

    # Berechne Gesamtgröße
    total_size = sum([b.file_size for b in backups.filter(status='completed')])
    stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)

    # Neustes erfolgreiches Backup
    last_successful = backups.filter(status='completed').first()
    stats['last_successful'] = last_successful

    # Handle Backup-Erstellung
    if request.method == 'POST':
        backup_type = request.POST.get('backup_type', 'full')

        try:
            out = StringIO()
            call_command(
                'backup_ldap',
                '--type=' + backup_type,
                '--username=' + request.user.username,
                '--notes=' + request.POST.get('notes', ''),
                stdout=out
            )
            messages.success(request, f'Backup "{backup_type}" wurde erfolgreich erstellt!')
        except Exception as e:
            messages.error(request, f'Backup fehlgeschlagen: {str(e)}')

        return redirect('backup_dashboard')

    context = {
        'backups': backups[:20],  # Nur die letzten 20 anzeigen
        'stats': stats,
        'backup_types': [
            ('full', 'Vollständig (alle Daten)'),
            ('users', 'Nur Benutzer'),
            ('groups', 'Nur Gruppen'),
            ('domains', 'Nur Mail-Domains'),
        ]
    }

    return render(request, 'backup/dashboard.html', context)


@login_required
@user_passes_test(is_ldap_admin)
def backup_download(request, backup_id):
    """
    Download eines Backups
    """
    from .models import LDAPBackup
    from django.http import FileResponse, Http404
    import os

    try:
        backup = LDAPBackup.objects.get(id=backup_id)

        if backup.status != 'completed':
            messages.error(request, 'Nur abgeschlossene Backups können heruntergeladen werden.')
            return redirect('backup_dashboard')

        if not os.path.exists(backup.file_path):
            messages.error(request, 'Backup-Datei nicht gefunden.')
            return redirect('backup_dashboard')

        response = FileResponse(open(backup.file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{backup.filename}"'
        return response

    except LDAPBackup.DoesNotExist:
        raise Http404("Backup nicht gefunden")


@login_required
@user_passes_test(is_ldap_admin)
def backup_delete(request, backup_id):
    """
    Lösche ein Backup (Datei + DB-Eintrag)
    """
    from .models import LDAPBackup

    try:
        backup = LDAPBackup.objects.get(id=backup_id)

        if request.method == 'POST':
            # Lösche Datei
            if backup.delete_file():
                messages.success(request, f'Backup-Datei "{backup.filename}" wurde gelöscht.')
            else:
                messages.warning(request, 'Backup-Datei konnte nicht gelöscht werden (existiert möglicherweise nicht).')

            # Lösche DB-Eintrag
            backup.delete()
            messages.success(request, 'Backup-Eintrag wurde aus der Datenbank entfernt.')

            return redirect('backup_dashboard')

        context = {
            'backup': backup
        }
        return render(request, 'backup/confirm_delete.html', context)

    except LDAPBackup.DoesNotExist:
        messages.error(request, 'Backup nicht gefunden.')
        return redirect('backup_dashboard')


@login_required
@user_passes_test(is_ldap_admin)
def backup_cleanup(request):
    """
    Lösche alte Backups, behalte nur die neuesten n
    """
    from .models import LDAPBackup

    if request.method == 'POST':
        keep_count = int(request.POST.get('keep_count', 10))

        deleted = LDAPBackup.cleanup_old_backups(keep_count)
        messages.success(request, f'{deleted} alte Backup(s) wurden gelöscht. Die neuesten {keep_count} wurden behalten.')

        return redirect('backup_dashboard')

    context = {
        'total_backups': LDAPBackup.objects.filter(status='completed').count()
    }
    return render(request, 'backup/cleanup.html', context)


@login_required
@user_passes_test(is_ldap_admin)
def backup_restore(request, backup_id):
    """
    Restore eines LDAP-Backups
    """
    from .models import LDAPBackup
    from django.core.management import call_command
    from io import StringIO
    import os

    try:
        backup = LDAPBackup.objects.get(id=backup_id)

        if backup.status != 'completed':
            messages.error(request, 'Nur abgeschlossene Backups koennen wiederhergestellt werden.')
            return redirect('backup_dashboard')

        if not os.path.exists(backup.file_path):
            messages.error(request, 'Backup-Datei nicht gefunden.')
            return redirect('backup_dashboard')

        if request.method == 'POST':
            confirm = request.POST.get('confirm', '')
            if confirm != 'RESTORE':
                messages.error(request, 'Bitte geben Sie RESTORE ein um die Wiederherstellung zu bestaetigen.')
                return render(request, 'backup/confirm_restore.html', {'backup': backup})

            try:
                out = StringIO()
                call_command(
                    'restore_ldap',
                    backup.file_path,
                    stdout=out
                )
                messages.success(request, f'Backup "{backup.filename}" wurde erfolgreich wiederhergestellt!')
            except Exception as e:
                messages.error(request, f'Restore fehlgeschlagen: {str(e)}')

            return redirect('backup_dashboard')

        return render(request, 'backup/confirm_restore.html', {'backup': backup})

    except LDAPBackup.DoesNotExist:
        messages.error(request, 'Backup nicht gefunden.')
        return redirect('backup_dashboard')
