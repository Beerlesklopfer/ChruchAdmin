import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings

from django.core import signing

from .models import PrivacyPolicy, LegalPage, ConsentLog, DeletionRequest

logger = logging.getLogger(__name__)


def privacy_policy(request):
    """Datenschutzerklaerung anzeigen (oeffentlich)"""
    policy = PrivacyPolicy.get_active()
    return render(request, 'privacy/privacy_policy.html', {
        'policy': policy,
    })


def impressum(request):
    """Impressum anzeigen (oeffentlich)"""
    page = LegalPage.get_page('impressum')
    return render(request, 'privacy/impressum.html', {'page': page})


def legal_page(request, page_type):
    """Beliebige rechtliche Seite anzeigen"""
    page = LegalPage.get_page(page_type)
    return render(request, 'privacy/impressum.html', {'page': page})


@login_required
def my_data(request):
    """DSGVO Auskunft: Zeigt dem User alle ueber ihn gespeicherten Daten"""
    from main.ldap_manager import LDAPManager

    user = request.user
    ldap_data = {}
    ldap_groups = []

    try:
        with LDAPManager() as ldap_mgr:
            user_data = ldap_mgr.get_user(user.username)
            if user_data:
                attrs = user_data['attributes']
                # Nur relevante Attribute anzeigen
                display_attrs = [
                    ('cn', 'Benutzername'),
                    ('givenName', 'Vorname'),
                    ('sn', 'Nachname'),
                    ('mail', 'Organisations-E-Mail'),
                    ('mailRoutingAddress', 'Private E-Mail'),
                    ('telephoneNumber', 'Telefon'),
                    ('mobile', 'Mobil'),
                    ('postalAddress', 'Anschrift'),
                    ('birthDate', 'Geburtstag'),
                    ('title', 'Rolle/Position'),
                    ('familyRole', 'Familienrolle'),
                ]
                for attr_key, attr_label in display_attrs:
                    val = attrs.get(attr_key, [])
                    if isinstance(val, list):
                        val = ', '.join(str(v) for v in val if v)
                    if val:
                        # Geburtstag aus LDAP-Format konvertieren
                        if attr_key == 'birthDate' and val:
                            try:
                                from datetime import datetime
                                dt = datetime.strptime(str(val)[:8], '%Y%m%d')
                                val = dt.strftime('%d.%m.%Y')
                            except (ValueError, TypeError):
                                pass
                        ldap_data[attr_label] = val

                # Gruppen
                member_of = attrs.get('memberOf', [])
                import re
                for group_dn in member_of:
                    if isinstance(group_dn, bytes):
                        group_dn = group_dn.decode('utf-8')
                    match = re.search(r'cn=([^,]+)', group_dn)
                    if match:
                        ldap_groups.append(match.group(1))
    except Exception as e:
        logger.error(f"Fehler beim Laden der LDAP-Daten fuer {user.username}: {e}")

    # Django-Daten
    django_data = {
        'Benutzername': user.username,
        'E-Mail': user.email,
        'Vorname': user.first_name,
        'Nachname': user.last_name,
        'Letzter Login': user.last_login.strftime('%d.%m.%Y %H:%M') if user.last_login else '-',
        'Registriert seit': user.date_joined.strftime('%d.%m.%Y %H:%M'),
    }

    # Einwilligungen
    consents = ConsentLog.objects.filter(user=user)

    # Aktueller Consent-Status (Opt-out: Standard = erteilt)
    consent_status = {}
    for ctype, clabel in ConsentLog.CONSENT_TYPES:
        latest = ConsentLog.objects.filter(user=user, consent_type=ctype).order_by('-timestamp').first()
        # Opt-out: Wenn kein Eintrag existiert, gilt als erteilt
        consent_status[ctype] = {
            'label': clabel,
            'granted': latest.granted if latest else True,
        }

    # Loeschantraege
    deletion_requests = DeletionRequest.objects.filter(user=user)

    # Familienmitglieder laden (fuer Familienoberhaupt)
    family_members = []
    family_consent_status = {}
    try:
        with LDAPManager() as ldap_mgr:
            user_data_fam = ldap_mgr.get_user(user.username)
            if user_data_fam:
                fam_role = user_data_fam['attributes'].get('familyRole', [''])[0]
                if isinstance(fam_role, bytes):
                    fam_role = fam_role.decode('utf-8')
                if fam_role == 'head':
                    children = ldap_mgr.list_users(parent_dn=user_data_fam['dn'])
                    from django.contrib.auth.models import User as DjangoUser
                    for child in children:
                        c_cn = child['attributes'].get('cn', [''])[0]
                        if isinstance(c_cn, bytes):
                            c_cn = c_cn.decode('utf-8')
                        c_given = child['attributes'].get('givenName', [''])[0]
                        if isinstance(c_given, bytes):
                            c_given = c_given.decode('utf-8')
                        c_sn = child['attributes'].get('sn', [''])[0]
                        if isinstance(c_sn, bytes):
                            c_sn = c_sn.decode('utf-8')

                        # Alter berechnen
                        c_birth = child['attributes'].get('birthDate', [''])[0]
                        if isinstance(c_birth, bytes):
                            c_birth = c_birth.decode('utf-8')
                        is_minor = True  # Default: minderjaehrig (darf verwaltet werden)
                        if c_birth:
                            try:
                                from datetime import datetime, date
                                bd = datetime.strptime(str(c_birth)[:8], '%Y%m%d').date()
                                today = date.today()
                                age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
                                is_minor = age < 16
                            except (ValueError, TypeError):
                                pass

                        # Consent-Status des Familienmitglieds
                        member_user = DjangoUser.objects.filter(username__iexact=c_cn).first()
                        member_consents = {}
                        for ctype, clabel in ConsentLog.CONSENT_TYPES:
                            if member_user:
                                latest = ConsentLog.objects.filter(user=member_user, consent_type=ctype).order_by('-timestamp').first()
                                member_consents[ctype] = latest.granted if latest else True
                            else:
                                member_consents[ctype] = True  # Opt-out default

                        family_members.append({
                            'cn': c_cn,
                            'name': f'{c_given} {c_sn}'.strip(),
                            'consents': member_consents,
                            'user_id': member_user.pk if member_user else None,
                            'is_minor': is_minor,
                        })
    except Exception:
        pass

    return render(request, 'privacy/my_data.html', {
        'ldap_data': ldap_data,
        'ldap_groups': ldap_groups,
        'django_data': django_data,
        'consents': consents,
        'consent_status': consent_status,
        'deletion_requests': deletion_requests,
        'family_members': family_members,
    })


@login_required
def export_my_data(request):
    """DSGVO Datenexport: Alle Daten als JSON herunterladen"""
    from main.ldap_manager import LDAPManager
    from django.http import HttpResponse

    user = request.user
    export = {
        'export_datum': timezone.now().isoformat(),
        'benutzer': {
            'benutzername': user.username,
            'email': user.email,
            'vorname': user.first_name,
            'nachname': user.last_name,
            'letzter_login': user.last_login.isoformat() if user.last_login else None,
            'registriert_seit': user.date_joined.isoformat(),
        },
        'ldap_daten': {},
        'gruppen': [],
        'einwilligungen': [],
    }

    try:
        with LDAPManager() as ldap_mgr:
            user_data = ldap_mgr.get_user(user.username)
            if user_data:
                attrs = user_data['attributes']
                for key, val in attrs.items():
                    if key in ('userPassword', 'jpegPhoto', 'objectClass'):
                        continue
                    if isinstance(val, list):
                        val = [str(v) for v in val if v]
                    export['ldap_daten'][key] = val

                member_of = attrs.get('memberOf', [])
                import re
                for group_dn in member_of:
                    if isinstance(group_dn, bytes):
                        group_dn = group_dn.decode('utf-8')
                    match = re.search(r'cn=([^,]+)', group_dn)
                    if match:
                        export['gruppen'].append(match.group(1))
    except Exception:
        pass

    for consent in ConsentLog.objects.filter(user=user):
        export['einwilligungen'].append({
            'typ': consent.get_consent_type_display(),
            'erteilt': consent.granted,
            'version': consent.policy_version,
            'zeitpunkt': consent.timestamp.isoformat(),
        })

    response = HttpResponse(
        json.dumps(export, indent=2, ensure_ascii=False),
        content_type='application/json; charset=utf-8'
    )
    response['Content-Disposition'] = f'attachment; filename="meine_daten_{user.username}.json"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def request_deletion(request):
    """Recht auf Vergessenwerden: Loeschantrag stellen"""
    # Pruefen ob bereits ein offener Antrag existiert
    existing = DeletionRequest.objects.filter(
        user=request.user, status__in=['pending', 'approved']
    ).first()

    if request.method == 'POST' and not existing:
        reason = request.POST.get('reason', '').strip()
        DeletionRequest.objects.create(
            user=request.user,
            username=request.user.username,
            email=request.user.email,
            reason=reason,
        )

        # Benachrichtigung an Admins
        try:
            from authapp.models import PermissionMapping
            from django.contrib.auth.models import User, Group
            from django.core.mail import send_mail

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

            if admin_emails:
                send_mail(
                    f'DSGVO Loeschantrag: {request.user.username}',
                    f'Benutzer: {request.user.get_full_name()} ({request.user.username})\n'
                    f'E-Mail: {request.user.email}\n'
                    f'Begruendung: {reason or "Keine Angabe"}\n\n'
                    f'Bitte bearbeiten Sie den Antrag im Admin-Bereich.',
                    settings.DEFAULT_FROM_EMAIL,
                    list(admin_emails),
                    fail_silently=True,
                )
        except Exception:
            pass

        messages.success(request, 'Ihr Loeschantrag wurde eingereicht. Sie werden benachrichtigt, sobald er bearbeitet wurde.')
        return redirect('privacy:my_data')

    return render(request, 'privacy/request_deletion.html', {
        'existing': existing,
    })


@login_required
def consent_update(request):
    """Einwilligung erteilen oder widerrufen (auch fuer Familienmitglieder)"""
    if request.method == 'POST':
        consent_type = request.POST.get('consent_type')
        granted = request.POST.get('granted') == 'true'
        target_user_id = request.POST.get('target_user_id')

        # Fuer Familienmitglied, per CN (Admin), oder sich selbst?
        from django.contrib.auth.models import User as DjangoUser
        target_user_cn = request.POST.get('target_user_cn')
        if target_user_id:
            target_user = DjangoUser.objects.filter(pk=target_user_id).first()
            if not target_user:
                messages.error(request, 'Benutzer nicht gefunden.')
                return redirect('privacy:my_data')
        elif target_user_cn:
            target_user = DjangoUser.objects.filter(username__iexact=target_user_cn).first()
            if not target_user:
                messages.error(request, f'Benutzer {target_user_cn} nicht gefunden.')
                return redirect('ldap_user_search')
        else:
            target_user = request.user

        policy = PrivacyPolicy.get_active()
        ConsentLog.objects.create(
            user=target_user,
            consent_type=consent_type,
            granted=granted,
            policy_version=policy.version if policy else '',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        name = target_user.get_full_name() or target_user.username
        action = 'erteilt' if granted else 'widerrufen'
        messages.success(request, f'Einwilligung fuer {name} {action}.')

        # Bei Widerruf von Datenverarbeitung/Datenschutzerklaerung -> Loeschantrag erstellen
        trigger_deletion = request.POST.get('trigger_deletion') == 'true'
        if trigger_deletion and not granted and consent_type in ('data_processing', 'privacy_policy'):
            existing = DeletionRequest.objects.filter(
                user=target_user, status__in=['pending', 'approved']
            ).first()
            if not existing:
                DeletionRequest.objects.create(
                    user=target_user,
                    username=target_user.username,
                    email=target_user.email,
                    reason=f'Automatisch erstellt: Einwilligung "{consent_type}" widerrufen',
                )
                messages.warning(request,
                    f'Da die Einwilligung zur Datenverarbeitung widerrufen wurde, '
                    f'wurde automatisch ein Loeschantrag fuer {name} erstellt. '
                    f'Die Gemeindeleitung wird benachrichtigt.')

                # Admin benachrichtigen
                try:
                    from authapp.models import PermissionMapping
                    from django.contrib.auth.models import Group
                    from django.core.mail import send_mail

                    admin_emails = set()
                    for group_name in PermissionMapping.get_groups_for_permission('manage_registrations'):
                        try:
                            for u in Group.objects.get(name=group_name).user_set.all():
                                if u.email: admin_emails.add(u.email)
                        except Group.DoesNotExist:
                            pass
                    for u in DjangoUser.objects.filter(is_superuser=True):
                        if u.email: admin_emails.add(u.email)

                    if admin_emails:
                        send_mail(
                            f'DSGVO: Datenverarbeitung widerrufen - {name}',
                            f'Der Benutzer {name} ({target_user.username}) hat die Einwilligung '
                            f'zur Datenverarbeitung widerrufen.\n\n'
                            f'Ein Loeschantrag wurde automatisch erstellt.\n'
                            f'Bitte bearbeiten Sie den Antrag zeitnah.',
                            settings.DEFAULT_FROM_EMAIL,
                            list(admin_emails),
                            fail_silently=True,
                        )
                except Exception:
                    pass

    if target_user_cn:
        return redirect('ldap_user_search')
    return redirect('privacy:my_data')


def generate_optout_token(user_id):
    """Generiert einen signierten Opt-out-Token fuer E-Mail-Links"""
    return signing.dumps({'uid': user_id, 'action': 'optout'}, salt='email-optout')


def optout_email(request, token):
    """Opt-out ueber E-Mail-Link (ohne Login)"""
    try:
        data = signing.loads(token, salt='email-optout', max_age=60*60*24*365)  # 1 Jahr gueltig
        from django.contrib.auth.models import User as DjangoUser
        user = DjangoUser.objects.get(pk=data['uid'])

        # Pruefen ob bereits widerrufen
        latest = ConsentLog.objects.filter(
            user=user, consent_type='email_communication'
        ).order_by('-timestamp').first()

        if latest and not latest.granted:
            return render(request, 'privacy/optout_result.html', {
                'success': True, 'already': True, 'username': user.get_full_name() or user.username,
            })

        # Consent widerrufen
        policy = PrivacyPolicy.get_active()
        ConsentLog.objects.create(
            user=user,
            consent_type='email_communication',
            granted=False,
            policy_version=policy.version if policy else '',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        logger.info(f"Opt-out per E-Mail-Link: {user.username}")

        return render(request, 'privacy/optout_result.html', {
            'success': True, 'already': False, 'username': user.get_full_name() or user.username,
        })

    except (signing.BadSignature, signing.SignatureExpired):
        return render(request, 'privacy/optout_result.html', {'success': False})
    except Exception as e:
        logger.error(f"Opt-out Fehler: {e}")
        return render(request, 'privacy/optout_result.html', {'success': False})
