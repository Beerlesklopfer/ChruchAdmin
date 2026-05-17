"""
Geraete-Konfiguration: Apple mobileconfig + Android Setup
Generiert personalisierte Konfigurations-Profile fuer E-Mail, CalDAV, CardDAV und WiFi.
"""
import uuid
import plistlib
import io
import base64
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings as django_settings

from main.ldap_manager import LDAPManager
from authapp.models import AppSettings, WiFiNetwork

logger = logging.getLogger(__name__)


def _get_autoconfig_settings():
    """Hole alle Autoconfig-Einstellungen aus AppSettings"""
    return {
        'imap_host': AppSettings.get('autoconfig_imap_host', ''),
        'imap_port': int(AppSettings.get('autoconfig_imap_port', '993')),
        'smtp_host': AppSettings.get('autoconfig_smtp_host', ''),
        'smtp_port': int(AppSettings.get('autoconfig_smtp_port', '465')),
        'caldav_url': AppSettings.get('autoconfig_caldav_url', ''),
        'church_name': AppSettings.get('church_name', 'Gemeinde'),
    }


def _build_email_payload(conf, user_attrs, password):
    """E-Mail (IMAP/SMTP) Payload"""
    return {
        'EmailAccountDescription': f'Mail {conf["church_name"]}',
        'EmailAccountName': user_attrs.get('displayName', ''),
        'EmailAccountType': 'EmailTypeIMAP',
        'EmailAddress': user_attrs.get('mail', ''),
        'IncomingMailServerAuthentication': 'EmailAuthPassword',
        'IncomingMailServerHostName': conf['imap_host'],
        'IncomingMailServerPortNumber': conf['imap_port'],
        'IncomingMailServerUseSSL': True,
        'IncomingMailServerUsername': user_attrs.get('mail', ''),
        'IncomingPassword': password,
        'OutgoingMailServerAuthentication': 'EmailAuthPassword',
        'OutgoingMailServerHostName': conf['smtp_host'],
        'OutgoingMailServerPortNumber': conf['smtp_port'],
        'OutgoingMailServerUsername': user_attrs.get('mail', ''),
        'OutgoingMailServerUseSSL': True,
        'OutgoingPassword': password,
        'OutgoingPasswordSameAsIncomingPassword': True,
        'PreventAppSheet': False,
        'PreventMove': False,
        'SMIMEEnabled': False,
        'SMIMEEncryptByDefault': False,
        'SMIMEEncryptByDefaultUserOverrideable': False,
        'SMIMESigningCertificateUUIDUserOverrideable': False,
        'SMIMESigningEnabled': False,
        'SMIMESigningUserOverrideable': False,
        'PayloadIdentifier': f'de.{django_settings.CHURCH_DOMAIN.replace(".", "-")}.mail',
        'PayloadType': 'com.apple.mail.managed',
        'PayloadUUID': str(uuid.uuid4()),
        'PayloadVersion': 1,
    }


def _build_caldav_payload(conf, user_attrs, password):
    """CalDAV (Kalender) Payload"""
    uid = user_attrs.get('entryUUID', user_attrs.get('uid', ''))
    caldav_url = conf['caldav_url'].rstrip('/')
    return {
        'CalDAVAccountDescription': f'Kalender {conf["church_name"]}',
        'CalDAVHostName': caldav_url,
        'CalDAVUsername': user_attrs.get('uid', ''),
        'CalDAVPassword': password,
        'CalDAVUseSSL': True,
        'CalDAVPort': 443,
        'CalDAVPrincipalURL': f'{caldav_url}/remote.php/dav/principals/users/{uid}/',
        'PayloadDisplayName': f'CalDAV - {conf["church_name"]}',
        'PayloadDescription': 'Konfiguriert CalDAV-Kalender',
        'PayloadIdentifier': f'de.{django_settings.CHURCH_DOMAIN.replace(".", "-")}.caldav',
        'PayloadType': 'com.apple.caldav.account',
        'PayloadOrganization': conf['church_name'],
        'PayloadUUID': str(uuid.uuid4()),
        'PayloadVersion': 1,
    }


def _build_carddav_payload(conf, user_attrs, password):
    """CardDAV (Kontakte) Payload"""
    caldav_url = conf['caldav_url'].rstrip('/')
    return {
        'CardDAVAccountDescription': f'Kontakte {conf["church_name"]}',
        'CardDAVHostName': caldav_url,
        'CardDAVUsername': user_attrs.get('uid', ''),
        'CardDAVPassword': password,
        'CardDAVUseSSL': True,
        'CardDAVPort': 443,
        'CardDAVPrincipalURL': '',
        'PayloadDisplayName': f'CardDAV - {conf["church_name"]}',
        'PayloadDescription': 'Konfiguriert CardDAV-Kontakte',
        'PayloadIdentifier': f'de.{django_settings.CHURCH_DOMAIN.replace(".", "-")}.carddav',
        'PayloadType': 'com.apple.carddav.account',
        'PayloadOrganization': conf['church_name'],
        'PayloadUUID': str(uuid.uuid4()),
        'PayloadVersion': 1,
    }


def _build_wifi_payload(wifi_network, conf):
    """WiFi Payload fuer ein einzelnes Netzwerk"""
    payload = {
        'AutoJoin': True,
        'EncryptionType': wifi_network.encryption_type if wifi_network.encryption_type != 'None' else 'None',
        'HIDDEN_NETWORK': wifi_network.is_hidden,
        'IsHotspot': False,
        'SSID_STR': wifi_network.ssid,
        'PayloadDisplayName': f'WiFi: {wifi_network.ssid}',
        'PayloadDescription': f'WLAN-Konfiguration fuer {wifi_network.ssid}',
        'PayloadIdentifier': f'de.{django_settings.CHURCH_DOMAIN.replace(".", "-")}.wifi.{wifi_network.pk}',
        'PayloadType': 'com.apple.wifi.managed',
        'PayloadUUID': str(uuid.uuid4()),
        'PayloadVersion': 1,
    }
    if wifi_network.password:
        payload['Password'] = wifi_network.password
    return payload


def _build_mobileconfig(user_attrs, password, services, conf):
    """Baut das komplette mobileconfig plist"""
    payload_content = []

    if 'email' in services and conf['imap_host']:
        payload_content.append(_build_email_payload(conf, user_attrs, password))

    if 'caldav' in services and conf['caldav_url']:
        payload_content.append(_build_caldav_payload(conf, user_attrs, password))

    if 'carddav' in services and conf['caldav_url']:
        payload_content.append(_build_carddav_payload(conf, user_attrs, password))

    # WiFi-Netzwerke
    wifi_ids = [s.replace('wifi_', '') for s in services if s.startswith('wifi_')]
    if wifi_ids:
        wifi_networks = WiFiNetwork.objects.filter(pk__in=wifi_ids, is_active=True)
        for network in wifi_networks:
            payload_content.append(_build_wifi_payload(network, conf))

    profile = {
        'PayloadDisplayName': f'Einstellungen {conf["church_name"]}',
        'PayloadDescription': 'iOS / macOS Konfiguration',
        'PayloadOrganization': conf['church_name'],
        'PayloadVersion': 1,
        'PayloadUUID': str(uuid.uuid4()),
        'PayloadType': 'Configuration',
        'PayloadIdentifier': f'de.{django_settings.CHURCH_DOMAIN.replace(".", "-")}.profile',
        'PayloadContent': payload_content,
    }

    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


@login_required
def download_mobileconfig(request):
    """Generiert und liefert ein personalisiertes .mobileconfig"""
    if request.method != 'POST':
        return redirect('profile')

    password = request.POST.get('config_password', '')
    if not password:
        messages.error(request, 'Bitte geben Sie Ihr Passwort ein.')
        return redirect('profile')

    # Ausgewaehlte Dienste
    services = request.POST.getlist('services')
    if not services:
        messages.error(request, 'Bitte waehlen Sie mindestens einen Dienst aus.')
        return redirect('profile')

    # LDAP-Authentifizierung pruefen
    from django.contrib.auth import authenticate
    user = authenticate(username=request.user.username, password=password)
    if user is None:
        messages.error(request, 'Falsches Passwort.')
        return redirect('profile')

    # LDAP-Daten holen
    try:
        with LDAPManager() as ldap:
            user_data = ldap.get_user(request.user.username)
            if not user_data:
                messages.error(request, 'LDAP-Benutzer nicht gefunden.')
                return redirect('profile')

            attrs = user_data['attributes']
            user_attrs = {}
            for key in ['cn', 'mail', 'uid', 'givenName', 'sn', 'displayName', 'entryUUID']:
                val = attrs.get(key, '')
                if isinstance(val, list):
                    val = val[0] if val else ''
                if isinstance(val, bytes):
                    val = val.decode('utf-8')
                user_attrs[key] = val

            if not user_attrs.get('displayName'):
                user_attrs['displayName'] = f"{user_attrs.get('givenName', '')} {user_attrs.get('sn', '')}"

    except Exception as e:
        logger.error(f"Fehler beim Laden der LDAP-Daten fuer mobileconfig: {e}")
        messages.error(request, 'Fehler beim Laden der Benutzerdaten.')
        return redirect('profile')

    conf = _get_autoconfig_settings()
    plist_data = _build_mobileconfig(user_attrs, password, services, conf)

    response = HttpResponse(plist_data, content_type='application/x-apple-aspen-config')
    response['Content-Disposition'] = f'attachment; filename="{conf["church_name"].lower().replace(" ", "-")}.mobileconfig"'
    return response


@login_required
def android_setup(request):
    """Android-Einrichtungsseite mit kopierbaren Feldern und Anleitung"""
    conf = _get_autoconfig_settings()
    wifi_networks = WiFiNetwork.objects.filter(is_active=True)

    # LDAP-Daten holen
    user_attrs = {}
    try:
        with LDAPManager() as ldap:
            user_data = ldap.get_user(request.user.username)
            if user_data:
                attrs = user_data['attributes']
                for key in ['cn', 'mail', 'uid', 'displayName']:
                    val = attrs.get(key, '')
                    if isinstance(val, list):
                        val = val[0] if val else ''
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    user_attrs[key] = val
    except Exception as e:
        logger.error(f"Fehler beim Laden der LDAP-Daten fuer Android-Setup: {e}")

    # WiFi-QR-Codes generieren
    wifi_qr_codes = []
    try:
        import qrcode
        import qrcode.image.svg
        for network in wifi_networks:
            factory = qrcode.image.svg.SvgPathImage
            img = qrcode.make(network.get_qr_string(), image_factory=factory, box_size=8)
            buf = io.BytesIO()
            img.save(buf)
            wifi_qr_codes.append({
                'network': network,
                'svg': buf.getvalue().decode('utf-8'),
            })
    except ImportError:
        logger.warning("qrcode-Bibliothek nicht installiert")

    return render(request, 'registration/android_setup.html', {
        'conf': conf,
        'user_attrs': user_attrs,
        'wifi_networks': wifi_networks,
        'wifi_qr_codes': wifi_qr_codes,
    })


@login_required
def wifi_network_list(request):
    """Admin: WiFi-Netzwerke verwalten"""
    networks = WiFiNetwork.objects.all()
    return render(request, 'ldap/wifi_networks.html', {
        'networks': networks,
    })


@login_required
def wifi_network_edit(request, pk=None):
    """Admin: WiFi-Netzwerk erstellen/bearbeiten"""
    network = None
    if pk:
        try:
            network = WiFiNetwork.objects.get(pk=pk)
        except WiFiNetwork.DoesNotExist:
            messages.error(request, 'WiFi-Netzwerk nicht gefunden.')
            return redirect('wifi_network_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        ssid = request.POST.get('ssid', '').strip()
        password = request.POST.get('password', '').strip()
        encryption_type = request.POST.get('encryption_type', 'WPA2')
        is_hidden = request.POST.get('is_hidden') == 'on'
        is_active = request.POST.get('is_active') == 'on'
        sort_order = int(request.POST.get('sort_order', 0))

        if not name or not ssid:
            messages.error(request, 'Name und SSID sind Pflichtfelder.')
        else:
            if network:
                network.name = name
                network.ssid = ssid
                network.password = password
                network.encryption_type = encryption_type
                network.is_hidden = is_hidden
                network.is_active = is_active
                network.sort_order = sort_order
                network.save()
                messages.success(request, f'WiFi-Netzwerk "{name}" wurde aktualisiert.')
            else:
                WiFiNetwork.objects.create(
                    name=name, ssid=ssid, password=password,
                    encryption_type=encryption_type, is_hidden=is_hidden,
                    is_active=is_active, sort_order=sort_order
                )
                messages.success(request, f'WiFi-Netzwerk "{name}" wurde erstellt.')
            return redirect('wifi_network_list')

    return render(request, 'ldap/wifi_network_edit.html', {
        'network': network,
        'encryption_choices': WiFiNetwork.ENCRYPTION_CHOICES,
    })


@login_required
def wifi_network_delete(request, pk):
    """Admin: WiFi-Netzwerk loeschen"""
    try:
        network = WiFiNetwork.objects.get(pk=pk)
        name = network.name
        network.delete()
        messages.success(request, f'WiFi-Netzwerk "{name}" wurde geloescht.')
    except WiFiNetwork.DoesNotExist:
        messages.error(request, 'WiFi-Netzwerk nicht gefunden.')
    return redirect('wifi_network_list')


def _build_wifi_qr_png_data_uri(qr_string, logo_path=None):
    """QR-Code mit hoher Error-Correction + zentriertem Logo als data:URI (PNG)."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H
    from PIL import Image

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=12,
        border=2,
    )
    qr.add_data(qr_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGBA')

    if logo_path:
        try:
            logo = Image.open(logo_path).convert('RGBA')
            qr_w, qr_h = img.size
            target = qr_w // 4
            logo.thumbnail((target, target), Image.LANCZOS)
            lw, lh = logo.size
            pad = max(8, lw // 12)
            bg = Image.new('RGBA', (lw + 2 * pad, lh + 2 * pad), (255, 255, 255, 255))
            bg.paste(logo, (pad, pad), logo)
            pos = ((qr_w - bg.size[0]) // 2, (qr_h - bg.size[1]) // 2)
            img.paste(bg, pos, bg)
        except Exception as e:
            logger.warning(f"Logo konnte nicht in QR-Code eingebettet werden: {e}")

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')


@login_required
def wifi_network_print(request, pk):
    """Admin: Druckansicht mit QR-Code und Gemeinde-Logo in der Mitte"""
    try:
        network = WiFiNetwork.objects.get(pk=pk)
    except WiFiNetwork.DoesNotExist:
        messages.error(request, 'WiFi-Netzwerk nicht gefunden.')
        return redirect('wifi_network_list')

    import os
    logo_path = os.path.join(django_settings.BASE_DIR, 'static', 'favicon', 'apple-touch-icon.png')
    if not os.path.exists(logo_path):
        logo_path = None

    qr_data_uri = _build_wifi_qr_png_data_uri(network.get_qr_string(), logo_path)

    return render(request, 'ldap/wifi_network_print.html', {
        'network': network,
        'qr_data_uri': qr_data_uri,
    })
