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


def require_permission(permission):
    """Decorator für Views, die eine bestimmte Berechtigung erfordern"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if has_permission(request.user, permission):
                return view_func(request, *args, **kwargs)
            else:
                from django.http import HttpResponseForbidden
                messages.error(request, f'Sie haben keine Berechtigung für diese Aktion ({permission}).')
                return redirect('ldap_dashboard')
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

                    # Bestimme Verwandtschaftsbeziehung und Parent aus DN
                    dn = user['dn']
                    relationship = 'Mitglied'  # Default
                    parent_name = None
                    parent_cn = None
                    if ',cn=' in dn:  # Nested User (Kind)
                        # Extrahiere Parent CN
                        parts = dn.split(',')
                        if len(parts) >= 2:
                            parent_cn_part = parts[1]
                            if parent_cn_part.startswith('cn='):
                                parent_cn = parent_cn_part[3:]
                                relationship = 'Kind'
                                parent_name = parent_cn.replace('.', ' ')

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
                        users.append({
                            'dn': user['dn'],
                            'uid': uid,
                            'cn': cn,
                            'mail': mail,
                            'givenName': given_name,
                            'sn': sn,
                            'title': title,
                            'telephoneNumber': telephone,
                            'mobile': mobile,
                            'postalAddress': postal_address,
                            'birthDate': birth_date,
                            'relationship': relationship,
                            'parent_name': parent_name,
                            'parent_cn': parent_cn or '',  # Für data-parent Attribut
                            'photo_base64': photo_base64,
                            'status': status,  # NEU: Status hinzugefügt
                        })

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP Verbindungsfehler: {str(e)}")
    except Exception as e:
        messages.error(request, f"LDAP Suchfehler: {str(e)}")

    # Pagination: 10 Benutzer pro Seite
    from django.core.paginator import Paginator
    paginator = Paginator(users, 10)  # 10 Einträge pro Seite
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'ldap/user_search.html', {
        'users': page_obj,  # Paginierte Benutzer
        'page_obj': page_obj,  # Für Pagination-Controls
        'search_query': search_query,
        'status_filter': status_filter,  # NEU: Status-Filter
        'all_users_for_parent': all_users_for_parent
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
    return render(request, 'home.html')

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
                    login(request, user)

                    # Log erfolgreichen Login
                    LDAPUserLog.objects.create(
                        user=user,
                        action='login',
                        details=f'Erfolgreicher LDAP-Login',
                        ip_address=request.META.get('REMOTE_ADDR')
                    )

                    messages.success(request, f'Willkommen zurück, {user.get_full_name() or user.username}!')
                    return redirect('ldap_dashboard')
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

                            print(f"DEBUG: LDAP Bind erfolgreich, logge User ein")

                            # LDAP Authentifizierung erfolgreich, logge User ein
                            # Setze backend attribute manuell
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
                            return redirect('ldap_dashboard')

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
    """Registrierung deaktivieren - nur LDAP Benutzer"""
    messages.error(request, "Registrierung ist deaktiviert. Bitte verwenden Sie LDAP zur Anmeldung.")
    return redirect('login')

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

                birth_date = attrs.get('birthDate', '')
                if isinstance(birth_date, list):
                    birth_date = birth_date[0] if birth_date else ''

                ldap_user_data = {
                    'cn': cn,
                    'givenName': given_name,
                    'sn': sn,
                    'mail': mail,
                    'title': title,
                    'telephoneNumber': telephone,
                    'mobile': mobile,
                    'postalAddress': postal_address,
                    'birthDate': birth_date,
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
        # Foto-Upload
        if 'jpegPhoto' in request.FILES:
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
    total_members = 0
    largest_family = {'member_count': 0}

    try:
        with LDAPManager() as ldap:
            # Hole alle Root-Benutzer (ohne Parent)
            all_users = ldap.list_users()

            # Finde alle Benutzer die Kinder haben (= Familienoberhäupter)
            for user in all_users:
                user_dn = user['dn']
                cn = user['attributes'].get('cn', [b''])[0]
                if isinstance(cn, bytes):
                    cn = cn.decode('utf-8')

                # Hole Kinder dieses Benutzers
                children = ldap.list_users(parent_dn=user_dn)

                if children:  # Nur wenn Kinder existieren
                    # Dekodiere Attribute
                    given_name = user['attributes'].get('givenName', [b''])[0]
                    sn = user['attributes'].get('sn', [b''])[0]
                    mail = user['attributes'].get('mail', [b''])[0]

                    if isinstance(given_name, bytes):
                        given_name = given_name.decode('utf-8')
                    if isinstance(sn, bytes):
                        sn = sn.decode('utf-8')
                    if isinstance(mail, bytes):
                        mail = mail.decode('utf-8')

                    family_name = sn or cn
                    member_count = len(children) + 1  # +1 für Elternteil
                    total_members += member_count

                    # Baue Kinder-Liste
                    children_list = []
                    for child in children:
                        child_cn = child['attributes'].get('cn', [b''])[0]
                        child_given_name = child['attributes'].get('givenName', [b''])[0]
                        child_sn = child['attributes'].get('sn', [b''])[0]
                        child_mail = child['attributes'].get('mail', [b''])[0]

                        if isinstance(child_cn, bytes):
                            child_cn = child_cn.decode('utf-8')
                        if isinstance(child_given_name, bytes):
                            child_given_name = child_given_name.decode('utf-8')
                        if isinstance(child_sn, bytes):
                            child_sn = child_sn.decode('utf-8')
                        if isinstance(child_mail, bytes):
                            child_mail = child_mail.decode('utf-8')

                        children_list.append({
                            'cn': child_cn,
                            'name': f"{child_given_name} {child_sn}",
                            'email': child_mail,
                        })

                    family = {
                        'head_cn': cn,
                        'name': family_name,
                        'head_name': f"{given_name} {sn}",
                        'head_email': mail,
                        'member_count': member_count,
                        'children': children_list,
                    }

                    families.append(family)

                    # Track größte Familie
                    if member_count > largest_family['member_count']:
                        largest_family = {'name': family_name, 'member_count': member_count}

    except LDAPConnectionError as e:
        messages.error(request, f"LDAP-Verbindungsfehler: {str(e)}")
    except Exception as e:
        messages.error(request, f"Fehler beim Laden der Familien: {str(e)}")

    context = {
        'families': families,
        'total_members': total_members,
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

    try:
        with LDAPManager() as ldap:
            user = ldap.get_user(cn)
            if not user:
                messages.error(request, 'Benutzer nicht gefunden.')
                return redirect('family_tree')

            # Dekodiere Attribute
            attributes = user['attributes']
            ldap_user = {
                'cn': cn,
                'givenName': attributes.get('givenName', [b''])[0].decode('utf-8') if isinstance(attributes.get('givenName', [b''])[0], bytes) else attributes.get('givenName', [''])[0],
                'sn': attributes.get('sn', [b''])[0].decode('utf-8') if isinstance(attributes.get('sn', [b''])[0], bytes) else attributes.get('sn', [''])[0],
                'mail': attributes.get('mail', [b''])[0].decode('utf-8') if isinstance(attributes.get('mail', [b''])[0], bytes) else attributes.get('mail', [''])[0],
                'displayName': attributes.get('displayName', [b''])[0].decode('utf-8') if isinstance(attributes.get('displayName', [b''])[0], bytes) else attributes.get('displayName', [''])[0],
                'photo_base64': ldap.get_photo_as_base64(cn),
            }

            if request.method == 'POST':
                # Update Attribute
                new_attributes = {
                    'givenName': request.POST.get('givenName'),
                    'sn': request.POST.get('sn'),
                    'mail': request.POST.get('mail', ''),
                    'displayName': f"{request.POST.get('givenName')} {request.POST.get('sn')}",
                }

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
                    new_attributes['birthDate'] = birth_date

                # Optional: Passwort ändern mit Validierung
                new_password = request.POST.get('password')
                new_password2 = request.POST.get('password2')
                if new_password or new_password2:
                    if new_password != new_password2:
                        messages.error(request, 'Die beiden Passwörter stimmen nicht überein.')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from django.http import JsonResponse
                            return JsonResponse({'success': False, 'error': 'Passwörter stimmen nicht überein'}, status=400)
                        return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user})
                    if len(new_password) < 8:
                        messages.error(request, 'Das Passwort muss mindestens 8 Zeichen lang sein.')
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            from django.http import JsonResponse
                            return JsonResponse({'success': False, 'error': 'Passwort zu kurz'}, status=400)
                        return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user})
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
                        return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user})

                ldap.update_user(cn, new_attributes)

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

    return render(request, 'ldap/user_edit.html', {'ldap_user': ldap_user})


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

    # Pagination: 10 Gruppen pro Seite
    from django.core.paginator import Paginator
    paginator = Paginator(groups, 10)  # 10 Einträge pro Seite
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    return render(request, 'ldap/group_list.html', {
        'groups': page_obj,  # Paginierte Gruppen
        'page_obj': page_obj,  # Für Pagination-Controls
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
