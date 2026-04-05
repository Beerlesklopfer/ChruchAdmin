"""
Password Reset Views
Sichere Passwort-Zurücksetzen-Funktionalität für LDAP-Benutzer
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from authapp.models import PasswordResetToken, AppSettings
from main.forms import PasswordResetRequestForm, PasswordResetConfirmForm
from main.ldap_manager import LDAPManager
from django.core.mail import get_connection, EmailMultiAlternatives


def get_client_ip(request):
    """Holt die Client-IP-Adresse aus dem Request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def password_reset_request(request):
    """
    Schritt 1: Benutzer gibt Email/Benutzername ein
    """
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            user = form.user

            # Aus Sicherheitsgründen immer Erfolgsmeldung zeigen
            # auch wenn kein Benutzer gefunden wurde
            if user:
                # Private E-Mail aus LDAP holen (erste mailRoutingAddress
                # die nicht auf @{settings.CHURCH_DOMAIN} endet)
                recipient_email = None
                try:
                    with LDAPManager() as ldap:
                        ldap_user = ldap.get_user(user.username)
                        if ldap_user:
                            attrs = ldap_user['attributes']
                            routing_addrs = attrs.get('mailRoutingAddress', [])
                            for addr in routing_addrs:
                                if isinstance(addr, bytes):
                                    addr = addr.decode('utf-8')
                                addr = addr.strip()
                                if addr and not addr.lower().endswith('@{settings.CHURCH_DOMAIN}'):
                                    recipient_email = addr
                                    break
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f'Password-Reset LDAP-Fehler für {user.username}: {e}')

                if not recipient_email:
                    # Kein mailRoutingAddress vorhanden — kein Versand
                    pass
                else:
                    # Erstelle Reset-Token
                    ip_address = get_client_ip(request)
                    token = PasswordResetToken.create_token(user, ip_address)

                    # Sende Reset-Email
                    reset_url = request.build_absolute_uri(
                        f'/password-reset/confirm/{token.token}/'
                    )

                    # Email-Text erstellen
                    subject = 'Passwort zurücksetzen - Church Admin'
                    html_message = render_to_string('emails/password_reset.html', {
                        'user': user,
                        'reset_url': reset_url,
                        'valid_hours': 24,
                    })
                    plain_message = strip_tags(html_message)

                    # E-Mail-Einstellungen aus AppSettings laden
                    from_email = AppSettings.get('email_from_address', settings.DEFAULT_FROM_EMAIL)
                    from_name = AppSettings.get('email_from_name', '')
                    if from_name:
                        from_email = f'{from_name} <{from_email}>'
                    reply_to = AppSettings.get('email_reply_to', '')

                    email_host = AppSettings.get('email_host', settings.EMAIL_HOST)
                    email_port = int(AppSettings.get('email_port', str(settings.EMAIL_PORT)))
                    email_use_tls = AppSettings.get('email_use_tls', 'false').lower() == 'true'
                    email_host_user = AppSettings.get('email_host_user', '')
                    email_host_password = AppSettings.get('email_host_password', '')

                    connection = get_connection(
                        host=email_host,
                        port=email_port,
                        username=email_host_user or None,
                        password=email_host_password or None,
                        use_tls=email_use_tls,
                    )

                    msg = EmailMultiAlternatives(
                        subject=subject,
                        body=plain_message,
                        from_email=from_email,
                        to=[recipient_email],
                        reply_to=[reply_to] if reply_to else [],
                        connection=connection,
                    )
                    msg.attach_alternative(html_message, 'text/html')
                    msg.send(fail_silently=False)

            # Immer gleiche Meldung (Sicherheit)
            messages.success(
                request,
                'Falls ein Konto mit dieser E-Mail-Adresse/Benutzernamen existiert, '
                'wurde eine E-Mail mit Anweisungen zum Zurücksetzen des Passworts versendet.'
            )
            return redirect('login')

    else:
        form = PasswordResetRequestForm()

    context = {
        'form': form,
        'title': 'Passwort zurücksetzen',
    }
    return render(request, 'auth/password_reset_request.html', context)


def password_reset_confirm(request, token):
    """
    Schritt 2: Benutzer setzt neues Passwort mit Token
    """
    # Hole Token aus DB
    reset_token = get_object_or_404(PasswordResetToken, token=token)

    # Prüfe ob Token gültig ist
    if not reset_token.is_valid():
        messages.error(
            request,
            'Dieser Link ist ungültig oder abgelaufen. '
            'Bitte fordern Sie einen neuen Link an.'
        )
        return redirect('password_reset_request')

    if request.method == 'POST':
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password1']

            try:
                # Setze Passwort im LDAP
                with LDAPManager() as ldap:
                    success = ldap.change_password(
                        reset_token.user.username,
                        new_password
                    )

                if success:
                    # Markiere Token als verwendet
                    reset_token.mark_as_used()

                    messages.success(
                        request,
                        'Ihr Passwort wurde erfolgreich geändert. '
                        'Sie können sich jetzt mit Ihrem neuen Passwort anmelden.'
                    )
                    return redirect('login')
                else:
                    messages.error(
                        request,
                        'Fehler beim Ändern des Passworts. Bitte kontaktieren Sie den Administrator.'
                    )
            except Exception as e:
                messages.error(
                    request,
                    f'Fehler beim Ändern des Passworts: {str(e)}'
                )

    else:
        form = PasswordResetConfirmForm()

    context = {
        'form': form,
        'token': token,
        'user': reset_token.user,
        'title': 'Neues Passwort setzen',
    }
    return render(request, 'auth/password_reset_confirm.html', context)
