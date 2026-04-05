import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.utils.html import strip_tags
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse

from .models import MailCampaign, MailLog, MailTemplate
from authapp.views import has_permission

logger = logging.getLogger(__name__)


def require_mailing_permission(view_func):
    """Decorator: Nur User mit send_massmail oder is_superuser"""
    def wrapper(request, *args, **kwargs):
        if has_permission(request.user, 'send_massmail') or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        messages.error(request, 'Sie haben keine Berechtigung fuer den Massen-E-Mail-Versand.')
        return redirect('user_dashboard')
    return wrapper


def _get_recipients_from_ldap(campaign):
    """Sammle Empfaenger-Adressen aus LDAP basierend auf Kampagne-Einstellungen"""
    from main.ldap_manager import LDAPManager

    recipients = []  # Liste von {'email': str, 'name': str}

    # recipient_type kann komma-getrennt sein (z.B. "members,visitors")
    types = [t.strip() for t in campaign.recipient_type.split(',') if t.strip()]

    # Manuelle Adressen sammeln
    if 'manual' in types:
        for line in campaign.recipient_emails_manual.strip().splitlines():
            email = line.strip()
            if email:
                recipients.append({'email': email, 'name': ''})
        # Wenn NUR manual, direkt zurueck
        if types == ['manual']:
            return recipients

    ldap_types = [t for t in types if t != 'manual']
    if not ldap_types:
        return recipients

    with LDAPManager() as ldap_mgr:
        all_users = ldap_mgr.list_users()

        # Mitglieder-Gruppe laden fuer Status-Bestimmung
        members_group = ldap_mgr.get_group(
            f"cn=Mitglieder,ou=Groups,{settings.LDAP_BASE_DN}")
        member_dns = set()
        if members_group:
            for m in members_group['attributes'].get('member', []):
                if isinstance(m, bytes):
                    m = m.decode('utf-8')
                member_dns.add(m.lower())

        # Bei Gruppen-Filter: Mitglieder der gewaehlten Gruppen laden
        group_member_dns = set()
        if 'groups' in ldap_types and campaign.recipient_groups:
            group_names = [g.strip() for g in campaign.recipient_groups.split(',') if g.strip()]
            for group_name in group_names:
                groups = ldap_mgr.list_groups(
                    filter_str=f"(cn={group_name})")
                for g in groups:
                    for m in g['attributes'].get('member', []):
                        if isinstance(m, bytes):
                            m = m.decode('utf-8')
                        group_member_dns.add(m.lower())

        for user in all_users:
            attrs = user['attributes']
            dn = user['dn'].lower()

            # Deaktivierte Accounts ueberspringen
            disabled = attrs.get('accountDisabled', [''])[0] if isinstance(
                attrs.get('accountDisabled', ['']), list) else attrs.get('accountDisabled', '')
            if isinstance(disabled, bytes):
                disabled = disabled.decode('utf-8')
            if disabled.upper() == 'TRUE':
                continue

            # Status bestimmen
            is_member = dn in member_dns
            family_role = attrs.get('familyRole', [''])[0] if isinstance(
                attrs.get('familyRole', ['']), list) else attrs.get('familyRole', '')

            # Pruefen ob User in mindestens einen der gewaehlten Typen passt
            matched = False
            for rtype in ldap_types:
                if rtype == 'all':
                    matched = True
                    break
                elif rtype == 'members':
                    if is_member or family_role in ('spouse', 'child'):
                        matched = True
                        break
                elif rtype == 'visitors':
                    if not is_member:
                        matched = True
                        break
                elif rtype == 'family':
                    if family_role in ('spouse', 'child', 'dependent') and not is_member:
                        matched = True
                        break
                elif rtype == 'guests':
                    if not is_member:
                        matched = True
                        break
                elif rtype == 'groups':
                    if dn in group_member_dns:
                        matched = True
                        break

            if not matched:
                continue

            # E-Mail-Adresse finden (bevorzugt mailRoutingAddress, dann mail)
            email = None
            routing_addrs = attrs.get('mailRoutingAddress', [])
            if isinstance(routing_addrs, list):
                for addr in routing_addrs:
                    if addr and '@{settings.CHURCH_DOMAIN}' not in addr:
                        email = addr
                        break
            if not email:
                mail_addrs = attrs.get('mail', [])
                if isinstance(mail_addrs, list) and mail_addrs:
                    email = mail_addrs[0]
                elif isinstance(mail_addrs, str) and mail_addrs:
                    email = mail_addrs

            if not email:
                continue

            given_name = attrs.get('givenName', [''])[0] if isinstance(
                attrs.get('givenName', ['']), list) else attrs.get('givenName', '')
            sn = attrs.get('sn', [''])[0] if isinstance(
                attrs.get('sn', ['']), list) else attrs.get('sn', '')
            cn = attrs.get('cn', [''])[0] if isinstance(
                attrs.get('cn', ['']), list) else attrs.get('cn', '')

            # Opt-out pruefen: Benutzer mit widerrufener E-Mail-Einwilligung ueberspringen
            from django.contrib.auth.models import User as DjangoUser
            from privacy.models import ConsentLog as CL
            dj_user = DjangoUser.objects.filter(username__iexact=cn).first()
            if dj_user:
                latest_consent = CL.objects.filter(
                    user=dj_user, consent_type='email_communication'
                ).order_by('-timestamp').first()
                if latest_consent and not latest_consent.granted:
                    continue

            recipients.append({
                'email': email,
                'name': f'{given_name} {sn}'.strip(),
                'cn': cn,
            })

    # Duplikate entfernen (nach E-Mail)
    seen = set()
    unique = []
    for r in recipients:
        if r['email'].lower() not in seen:
            seen.add(r['email'].lower())
            unique.append(r)

    return unique


def _personalize_html(html, name):
    """Ersetze Platzhalter im HTML"""
    parts = name.split(' ', 1) if name else ['', '']
    first_name = parts[0] if parts else ''
    last_name = parts[1] if len(parts) > 1 else ''
    html = html.replace('[[vorname]]', first_name)
    html = html.replace('[[nachname]]', last_name)
    html = html.replace('[[name]]', name)
    return html


@login_required
@require_mailing_permission
def campaign_list(request):
    """Uebersicht aller Kampagnen"""
    campaigns = MailCampaign.objects.all()
    return render(request, 'mailing/campaign_list.html', {
        'campaigns': campaigns,
    })


@login_required
@require_mailing_permission
def campaign_compose(request, pk=None):
    """Neue Kampagne erstellen oder bestehenden Entwurf bearbeiten"""
    from main.ldap_manager import LDAPManager

    campaign = None
    if pk:
        campaign = get_object_or_404(MailCampaign, pk=pk)
        if campaign.status != 'draft':
            messages.error(request, 'Nur Entwuerfe koennen bearbeitet werden.')
            return redirect('mailing:campaign_detail', pk=pk)

    from authapp.models import AppSettings
    church = AppSettings.get('church_name', 'Bibelgemeinde Lage')
    DEFAULT_FOOTER = (
        '<div style="text-align:center; font-size:11px; color:#999; padding:20px; '
        'border-top:1px solid #ddd; margin-top:20px;">'
        f'<p><strong>{church}</strong></p>'
        f'<p>Sie erhalten diese E-Mail als Mitglied oder Angehoeriger der {church}. '
        'Ihre Daten werden gemaess der DSGVO verarbeitet und nicht an Dritte weitergegeben.</p>'
        f'<p>&copy; 2026 {church}</p></div>'
    )
    footer_default = campaign.footer_html if campaign and campaign.footer_html else DEFAULT_FOOTER

    # LDAP-Gruppen laden fuer Auswahl
    groups = []
    try:
        with LDAPManager() as ldap_mgr:
            ldap_groups = ldap_mgr.list_groups()
            for g in ldap_groups:
                cn = g['attributes'].get('cn', [''])[0] if isinstance(
                    g['attributes'].get('cn', ['']), list) else g['attributes'].get('cn', '')
                if cn and cn != 'nobody':
                    groups.append(cn)
            groups.sort()
    except Exception:
        pass

    # Vorlagen laden
    templates = MailTemplate.objects.all()

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body_html = request.POST.get('body_html', '').strip()
        recipient_type = request.POST.get('recipient_type', 'members')
        recipient_groups = request.POST.get('recipient_groups', '')
        recipient_emails_manual = request.POST.get('recipient_emails_manual', '')
        from_name = request.POST.get('from_name', 'Bibelgemeinde Lage').strip()
        reply_to = request.POST.get('reply_to', '').strip()
        footer_html = request.POST.get('footer_html', '').strip()

        if not subject:
            messages.error(request, 'Bitte geben Sie einen Betreff ein.')
            return render(request, 'mailing/campaign_compose.html', {
                'campaign': campaign, 'groups': groups, 'templates': templates, 'footer_default': footer_default,
            })
        if not body_html:
            messages.error(request, 'Bitte geben Sie einen Inhalt ein.')
            return render(request, 'mailing/campaign_compose.html', {
                'campaign': campaign, 'groups': groups, 'templates': templates, 'footer_default': footer_default,
            })

        if campaign:
            campaign.subject = subject
            campaign.body_html = body_html
            campaign.body_text = strip_tags(body_html)
            campaign.recipient_type = recipient_type
            campaign.recipient_groups = recipient_groups
            campaign.recipient_emails_manual = recipient_emails_manual
            campaign.from_name = from_name
            campaign.reply_to = reply_to
            campaign.footer_html = footer_html
            campaign.save()
        else:
            campaign = MailCampaign.objects.create(
                subject=subject,
                body_html=body_html,
                body_text=strip_tags(body_html),
                recipient_type=recipient_type,
                recipient_groups=recipient_groups,
                recipient_emails_manual=recipient_emails_manual,
                from_name=from_name,
                reply_to=reply_to,
                footer_html=footer_html,
                created_by=request.user,
            )

        action = request.POST.get('action', 'save')
        if action == 'preview':
            return redirect('mailing:campaign_preview', pk=campaign.pk)
        elif action == 'send':
            return redirect('mailing:campaign_send', pk=campaign.pk)

        messages.success(request, 'Entwurf gespeichert.')
        return redirect('mailing:campaign_list')

    return render(request, 'mailing/campaign_compose.html', {
        'campaign': campaign,
        'groups': groups,
        'templates': templates,
        'footer_default': footer_default,
    })


@login_required
@require_mailing_permission
def campaign_preview(request, pk):
    """Vorschau der Kampagne mit Empfaengerliste"""
    campaign = get_object_or_404(MailCampaign, pk=pk)
    recipients = _get_recipients_from_ldap(campaign)

    return render(request, 'mailing/campaign_preview.html', {
        'campaign': campaign,
        'recipients': recipients,
        'recipient_count': len(recipients),
    })


@login_required
@require_mailing_permission
def campaign_test(request, pk):
    """Test-Mail an den aktuellen Benutzer senden"""
    campaign = get_object_or_404(MailCampaign, pk=pk)

    test_email = request.user.email
    if not test_email:
        # Versuche aus LDAP
        try:
            from main.ldap_manager import LDAPManager
            with LDAPManager() as ldap_mgr:
                user_data = ldap_mgr.get_user(request.user.username)
                if user_data:
                    addrs = user_data['attributes'].get('mailRoutingAddress', [])
                    for a in (addrs if isinstance(addrs, list) else [addrs]):
                        if a and '@{settings.CHURCH_DOMAIN}' not in a:
                            test_email = a
                            break
        except Exception:
            pass

    if not test_email:
        messages.error(request, 'Keine E-Mail-Adresse fuer Test-Versand gefunden.')
        return redirect('mailing:campaign_preview', pk=pk)

    try:
        user_name = request.user.get_full_name() or request.user.username
        html = _personalize_html(campaign.body_html, user_name)
        if campaign.footer_html:
            html += campaign.footer_html

        # Opt-out-Link auch in Test-Mail
        from privacy.views import generate_optout_token
        from authapp.models import AppSettings as AS
        _church = AS.get('church_name', 'Bibelgemeinde Lage')
        token = generate_optout_token(request.user.pk)
        optout_url = request.build_absolute_uri(f'/datenschutz/optout/{token}/')
        dsgvo_url = request.build_absolute_uri('/datenschutz/my-data/')
        html += (
            f'<div style="text-align:center; font-size:10px; color:#aaa; margin-top:10px; padding:10px; border-top:1px solid #eee;">'
            f'Sie erhalten diese E-Mail als Mitglied der {_church}. '
            f'<a href="{dsgvo_url}" style="color:#aaa;">Einstellungen verwalten</a> | '
            f'<a href="{optout_url}" style="color:#aaa;">Abmelden</a></div>'
        )

        plain = strip_tags(html)

        from_email = f'{campaign.from_name} <{settings.DEFAULT_FROM_EMAIL}>'
        msg = EmailMultiAlternatives(
            subject=f'[TEST] {campaign.subject}',
            body=plain,
            from_email=from_email,
            to=[test_email],
        )
        if campaign.reply_to:
            msg.reply_to = [campaign.reply_to]
        msg.attach_alternative(html, 'text/html')
        msg.send()

        messages.success(request, f'Test-Mail gesendet an {test_email}')
    except Exception as e:
        messages.error(request, f'Fehler beim Test-Versand: {e}')

    return redirect('mailing:campaign_preview', pk=pk)


@login_required
@require_mailing_permission
@require_http_methods(["GET", "POST"])
def campaign_send(request, pk):
    """Kampagne absenden"""
    campaign = get_object_or_404(MailCampaign, pk=pk)

    if campaign.status not in ('draft', 'failed'):
        messages.error(request, 'Diese Kampagne kann nicht (erneut) versendet werden.')
        return redirect('mailing:campaign_detail', pk=pk)

    if request.method == 'GET':
        recipients = _get_recipients_from_ldap(campaign)
        return render(request, 'mailing/campaign_send_confirm.html', {
            'campaign': campaign,
            'recipient_count': len(recipients),
        })

    # POST: Versand starten
    recipients = _get_recipients_from_ldap(campaign)
    if not recipients:
        messages.error(request, 'Keine Empfaenger gefunden.')
        return redirect('mailing:campaign_preview', pk=pk)

    campaign.status = 'sending'
    campaign.total_recipients = len(recipients)
    campaign.successful_count = 0
    campaign.failed_count = 0
    campaign.save()

    # Alte Logs loeschen (bei erneutem Versand)
    campaign.logs.all().delete()

    from_email = f'{campaign.from_name} <{settings.DEFAULT_FROM_EMAIL}>'
    success = 0
    failed = 0

    from django.contrib.auth.models import User as DjangoUser
    from privacy.views import generate_optout_token

    for recipient in recipients:
        try:
            html = _personalize_html(campaign.body_html, recipient['name'])
            if campaign.footer_html:
                html += campaign.footer_html

            # Opt-out-Link einfuegen
            django_user = DjangoUser.objects.filter(username__iexact=recipient.get('cn', '')).first()
            if django_user:
                from authapp.models import AppSettings as AS
                _church = AS.get('church_name', 'Bibelgemeinde Lage')
                token = generate_optout_token(django_user.pk)
                optout_url = request.build_absolute_uri(f'/datenschutz/optout/{token}/')
                dsgvo_url = request.build_absolute_uri('/datenschutz/my-data/')
                html += (
                    f'<div style="text-align:center; font-size:10px; color:#aaa; margin-top:10px; padding:10px; border-top:1px solid #eee;">'
                    f'Sie erhalten diese E-Mail als Mitglied der {_church}. '
                    f'<a href="{dsgvo_url}" style="color:#aaa;">Einstellungen verwalten</a> | '
                    f'<a href="{optout_url}" style="color:#aaa;">Abmelden</a></div>'
                )

            plain = strip_tags(html)

            msg = EmailMultiAlternatives(
                subject=campaign.subject,
                body=plain,
                from_email=from_email,
                to=[recipient['email']],
            )
            if campaign.reply_to:
                msg.reply_to = [campaign.reply_to]
            msg.attach_alternative(html, 'text/html')
            msg.send()

            MailLog.objects.create(
                campaign=campaign,
                recipient_email=recipient['email'],
                recipient_name=recipient['name'],
                status='sent',
                sent_at=timezone.now(),
            )
            success += 1

        except Exception as e:
            MailLog.objects.create(
                campaign=campaign,
                recipient_email=recipient['email'],
                recipient_name=recipient['name'],
                status='failed',
                error_message=str(e),
                sent_at=timezone.now(),
            )
            failed += 1
            logger.error(f"Mail an {recipient['email']} fehlgeschlagen: {e}")

    campaign.successful_count = success
    campaign.failed_count = failed
    campaign.sent_at = timezone.now()
    campaign.status = 'sent' if failed == 0 else ('failed' if success == 0 else 'sent')
    campaign.save()

    if failed == 0:
        messages.success(request, f'Kampagne erfolgreich an {success} Empfaenger versendet.')
    else:
        messages.warning(request, f'{success} zugestellt, {failed} fehlgeschlagen.')

    return redirect('mailing:campaign_detail', pk=pk)


@login_required
@require_mailing_permission
def campaign_detail(request, pk):
    """Kampagne-Details mit Versandprotokoll"""
    campaign = get_object_or_404(MailCampaign, pk=pk)
    logs = campaign.logs.all()

    return render(request, 'mailing/campaign_detail.html', {
        'campaign': campaign,
        'logs': logs,
        'sent_logs': logs.filter(status='sent'),
        'failed_logs': logs.filter(status='failed'),
    })


@login_required
@require_mailing_permission
@require_http_methods(["POST"])
def campaign_delete(request, pk):
    """Kampagne loeschen"""
    campaign = get_object_or_404(MailCampaign, pk=pk)
    campaign.delete()
    messages.success(request, 'Kampagne geloescht.')
    return redirect('mailing:campaign_list')


@login_required
@require_mailing_permission
@require_http_methods(["POST"])
def campaign_duplicate(request, pk):
    """Kampagne duplizieren als neuen Entwurf"""
    original = get_object_or_404(MailCampaign, pk=pk)
    copy = MailCampaign.objects.create(
        subject=f'Kopie: {original.subject}',
        body_html=original.body_html,
        body_text=original.body_text,
        recipient_type=original.recipient_type,
        recipient_groups=original.recipient_groups,
        recipient_emails_manual=original.recipient_emails_manual,
        from_name=original.from_name,
        reply_to=original.reply_to,
        created_by=request.user,
        status='draft',
    )
    messages.success(request, f'Kampagne dupliziert als Entwurf.')
    return redirect('mailing:campaign_compose', pk=copy.pk)


# --- Template-Verwaltung ---

@login_required
@require_mailing_permission
def template_list(request):
    """Liste aller Mail-Vorlagen"""
    templates = MailTemplate.objects.all()
    return render(request, 'mailing/template_list.html', {
        'templates': templates,
    })


@login_required
@require_mailing_permission
def template_edit(request, pk=None):
    """Vorlage erstellen oder bearbeiten"""
    template = None
    if pk:
        template = get_object_or_404(MailTemplate, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        subject = request.POST.get('subject', '').strip()
        body_html = request.POST.get('body_html', '').strip()
        description = request.POST.get('description', '').strip()

        if not name or not subject or not body_html:
            messages.error(request, 'Name, Betreff und Inhalt sind Pflichtfelder.')
            return render(request, 'mailing/template_edit.html', {'template': template})

        if template:
            template.name = name
            template.subject = subject
            template.body_html = body_html
            template.description = description
            template.save()
        else:
            template = MailTemplate.objects.create(
                name=name, subject=subject, body_html=body_html,
                description=description, created_by=request.user,
            )

        messages.success(request, 'Vorlage gespeichert.')
        return redirect('mailing:template_list')

    return render(request, 'mailing/template_edit.html', {'template': template})


@login_required
@require_mailing_permission
@require_http_methods(["POST"])
def template_delete(request, pk):
    """Vorlage loeschen"""
    template = get_object_or_404(MailTemplate, pk=pk)
    template.delete()
    messages.success(request, 'Vorlage geloescht.')
    return redirect('mailing:template_list')


@login_required
@require_mailing_permission
def template_load(request, pk):
    """Vorlage als JSON laden (AJAX)"""
    template = get_object_or_404(MailTemplate, pk=pk)
    return JsonResponse({
        'subject': template.subject,
        'body_html': template.body_html,
    })
