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
from authapp.models import PasswordResetToken
from main.forms import PasswordResetRequestForm, PasswordResetConfirmForm
from main.ldap_manager import LDAPManager


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

                send_mail(
                    subject,
                    plain_message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    html_message=html_message,
                    fail_silently=False,
                )

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
