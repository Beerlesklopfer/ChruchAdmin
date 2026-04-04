"""
Gemeindelisten-Export Views
PDF und vCard/CardDAV Export
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# DejaVuSans registrieren fuer Unicode-Symbole
try:
    pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
except:
    pass
from reportlab.lib.enums import TA_CENTER
import vobject

from main.ldap_manager import LDAPManager, LDAPConnectionError
from authapp.models import MemberListExportSettings
from authapp.views import has_permission, is_ldap_admin


@login_required
def member_list_export(request):
    """
    Gemeindelisten-Export Übersicht
    Zeigt verfügbare Export-Konfigurationen und ermöglicht Export
    """
    if not has_permission(request.user, 'export_members'):
        messages.error(request, 'Sie haben keine Berechtigung, die Gemeindeliste zu exportieren.')
        return redirect('home')

    # Hole verfügbare Export-Konfigurationen
    if request.user.is_superuser or has_permission(request.user, 'manage_users'):
        export_settings = MemberListExportSettings.objects.all()
    else:
        export_settings = MemberListExportSettings.objects.filter(is_public=True)

    context = {
        'export_settings': export_settings,
    }

    return render(request, 'ldap/member_list_export.html', context)


@login_required
def member_list_export_pdf(request, settings_id=None):
    """
    Export der Gemeindeliste als PDF
    """
    if not has_permission(request.user, 'export_members'):
        messages.error(request, 'Sie haben keine Berechtigung, die Gemeindeliste zu exportieren.')
        return redirect('home')

    # Hole Export-Einstellungen
    if settings_id:
        try:
            export_settings = MemberListExportSettings.objects.get(pk=settings_id)
        except MemberListExportSettings.DoesNotExist:
            messages.error(request, 'Export-Einstellungen nicht gefunden.')
            return redirect('member_list_export')
    else:
        # Standard-Einstellungen: Alle Felder
        export_settings = type('obj', (object,), {
            'name': 'Standard-Export',
            'include_name': True,
            'include_email': True,
            'include_phone': True,
            'include_address': True,
            'include_birthday': True,
            'include_groups': True,
            'include_family': True,
            'user_filter': 'members',
            'sort_by': 'sn',
        })()

    # Hole Benutzer aus LDAP
    users_data = []
    try:
        with LDAPManager() as ldap:
            all_users = ldap.list_users()

            # Filter anwenden
            filtered_users = []
            if export_settings.user_filter == 'members':
                # Mitglieder + deren Familien (Kinder/Ehepartner)
                members_group = ldap.get_group(f"cn=Mitglieder,ou=Groups,dc=example-church,dc=de")
                if members_group:
                    member_dns = members_group['attributes'].get('member', [])
                    member_dns_set = set()
                    for d in member_dns:
                        member_dns_set.add(d.decode('utf-8') if isinstance(d, bytes) else d)
                    # Sammle DNs der Mitglieder und deren Familien
                    family_dns = set()
                    for user in all_users:
                        if user['dn'] in member_dns_set:
                            family_dns.add(user['dn'])
                            # Familienmitglieder (Kinder unter diesem User)
                            children = ldap.list_users(parent_dn=user['dn'])
                            for c in children:
                                family_dns.add(c['dn'])
                            # Falls User nested ist, auch das Oberhaupt einschliessen
                            if ',cn=' in user['dn']:
                                parts = user['dn'].split(',', 1)
                                parent_dn = parts[1] if len(parts) > 1 else None
                                if parent_dn:
                                    # Auch Geschwister
                                    siblings = ldap.list_users(parent_dn=parent_dn)
                                    for s in siblings:
                                        family_dns.add(s['dn'])
                                    family_dns.add(parent_dn)
                    for user in all_users:
                        if user['dn'] in family_dns:
                            filtered_users.append(user)
            elif export_settings.user_filter == 'visitors':
                visitors_group = ldap.get_group(f"cn=Besucher,ou=Groups,dc=example-church,dc=de")
                if visitors_group:
                    visitor_dns = visitors_group['attributes'].get('member', [])
                    for user in all_users:
                        if user['dn'].encode('utf-8') in visitor_dns or user['dn'] in visitor_dns:
                            filtered_users.append(user)
            elif export_settings.user_filter == 'family_heads':
                for user in all_users:
                    children = ldap.list_users(parent_dn=user['dn'])
                    if children:
                        filtered_users.append(user)
            else:  # all
                filtered_users = all_users

            # Sortierung
            sort_field = export_settings.sort_by
            filtered_users.sort(key=lambda u: u['attributes'].get(sort_field, [b''])[0].decode('utf-8') if isinstance(u['attributes'].get(sort_field, [b''])[0], bytes) else u['attributes'].get(sort_field, [''])[0])

            # Daten extrahieren
            for user in filtered_users:
                attrs = user['attributes']

                # Dekodiere Basis-Felder
                def _d(attr_name):
                    val = attrs.get(attr_name, [b''])[0]
                    if isinstance(val, bytes):
                        val = val.decode('utf-8')
                    return val or ''

                given_name = _d('givenName')
                sn = _d('sn')
                mail = _d('mail')
                phone = _d('telephoneNumber')
                mobile = _d('mobile')
                postal = _d('postalAddress')
                birth_raw = _d('birthDate')

                birth_display = ''
                if birth_raw:
                    try:
                        from datetime import datetime
                        birth_display = datetime.strptime(str(birth_raw)[:8], '%Y%m%d').strftime('%d.%m.%Y')
                    except (ValueError, TypeError):
                        birth_display = birth_raw

                user_dict = {}

                if export_settings.include_name:
                    family_role = _d('familyRole')
                    role_icon = ''
                    if family_role == 'head':
                        role_icon = ' \u2605'       # ★
                    elif family_role == 'spouse':
                        role_icon = ' \u2665'       # ♥
                    elif family_role == 'child' or (',cn=' in user['dn'] and family_role != 'head'):
                        role_icon = ' \u21b3'       # ↳
                    user_dict['name'] = f"{sn}, {given_name}{role_icon}"
                if export_settings.include_email:
                    user_dict['email'] = mail
                if export_settings.include_phone:
                    user_dict['phone'] = phone
                    user_dict['mobile'] = mobile
                if export_settings.include_address:
                    user_dict['address'] = postal.replace('\n', ', ')
                if export_settings.include_birthday:
                    user_dict['birthday'] = birth_display

                # Gruppen
                if export_settings.include_groups:
                    member_of = attrs.get('memberOf', [])
                    groups = []
                    for group_dn in member_of:
                        if isinstance(group_dn, bytes):
                            group_dn = group_dn.decode('utf-8')
                        import re
                        match = re.search(r'cn=([^,]+)', group_dn)
                        if match:
                            groups.append(match.group(1))
                    user_dict['groups'] = ', '.join(groups) if groups else '-'

                users_data.append(user_dict)

    except Exception as e:
        messages.error(request, f'Fehler beim Laden der Daten: {str(e)}')
        return redirect('member_list_export')

    # PDF erstellen
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="gemeindeliste_{export_settings.name.replace(" ", "_")}.pdf"'

    # PDF-Dokument mit Header auf jeder Seite
    from reportlab.lib.pagesizes import landscape
    from datetime import datetime as dt_now

    def page_header(canvas, doc):
        canvas.saveState()
        canvas.setFont('DejaVu-Bold', 12)
        canvas.setFillColor(colors.HexColor('#1c2647'))
        canvas.drawString(1.5*cm, landscape(A4)[1] - 1*cm, "Gemeindeliste - Beispielgemeinde")
        canvas.setFont('DejaVu', 8)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(landscape(A4)[0] - 1.5*cm, landscape(A4)[1] - 1*cm, f"Stand: {dt_now.now().strftime('%d.%m.%Y')}")
        canvas.drawRightString(landscape(A4)[0] - 1.5*cm, 0.8*cm, f"Seite {canvas.getPageNumber()}")
        canvas.restoreState()

    doc = SimpleDocTemplate(response, pagesize=landscape(A4), topMargin=1.8*cm, bottomMargin=1.5*cm, leftMargin=1.5*cm, rightMargin=1.5*cm)
    elements = []

    # Styles
    styles = getSampleStyleSheet()

    # Tabelle erstellen
    table_data = []

    # Header
    header = []
    if export_settings.include_name:
        header.append('Name')
    if export_settings.include_email:
        header.append('E-Mail')
    if export_settings.include_phone:
        header.append('Telefon')
        header.append('Mobil')
    if export_settings.include_address:
        header.append('Anschrift')
    if export_settings.include_birthday:
        header.append('Geburtstag')
    if export_settings.include_groups:
        header.append('Gruppen')
    table_data.append(header)

    # Daten
    for user in users_data:
        row = []
        if export_settings.include_name:
            row.append(user.get('name', ''))
        if export_settings.include_email:
            row.append(user.get('email', ''))
        if export_settings.include_phone:
            row.append(user.get('phone', ''))
            row.append(user.get('mobile', ''))
        if export_settings.include_address:
            row.append(user.get('address', ''))
        if export_settings.include_birthday:
            row.append(user.get('birthday', ''))
        if export_settings.include_groups:
            row.append(user.get('groups', ''))
        table_data.append(row)

    # Spaltenbreiten berechnen fuer volle Seitenbreite
    page_width = landscape(A4)[0] - 3*cm  # Seitenbreite minus Raender
    col_count = len(header)
    # Proportionale Breiten: Name breit, Geburtstag/Gruppen schmal
    col_widths = None
    if col_count > 0:
        widths = {
            'Name': 3.5*cm,
            'E-Mail': 5.5*cm,
            'Telefon': 3*cm,
            'Mobil': 3*cm,
            'Anschrift': 4.5*cm,
            'Geburtstag': 2.2*cm,
            'Gruppen': 3*cm,
        }
        col_widths = [widths.get(h, page_width / col_count) for h in header]
        # Restbreite auf Anschrift verteilen
        used = sum(col_widths)
        if used < page_width and 'Anschrift' in header:
            idx = header.index('Anschrift')
            col_widths[idx] += page_width - used

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2647')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f3e6')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    elements.append(table)

    # PDF bauen
    doc.build(elements, onFirstPage=page_header, onLaterPages=page_header)

    return response


@login_required
def member_list_export_vcard(request, settings_id=None):
    """
    Export der Gemeindeliste als vCard/CardDAV
    """
    if not has_permission(request.user, 'export_members'):
        messages.error(request, 'Sie haben keine Berechtigung, die Gemeindeliste zu exportieren.')
        return redirect('home')

    # Hole Export-Einstellungen
    if settings_id:
        try:
            export_settings = MemberListExportSettings.objects.get(pk=settings_id)
        except MemberListExportSettings.DoesNotExist:
            messages.error(request, 'Export-Einstellungen nicht gefunden.')
            return redirect('member_list_export')
    else:
        # Standard-Einstellungen
        export_settings = type('obj', (object,), {
            'include_name': True,
            'include_email': True,
            'include_phone': True,
            'include_address': True,
            'include_birthday': True,
            'user_filter': 'members',
            'sort_by': 'sn',
        })()

    # Hole Benutzer aus LDAP und erstelle vCards
    vcards = []
    try:
        with LDAPManager() as ldap:
            all_users = ldap.list_users()

            # Filter anwenden (wie bei PDF)
            filtered_users = []
            if export_settings.user_filter == 'all':
                filtered_users = all_users
            elif export_settings.user_filter == 'members':
                members_group = ldap.get_group(f"cn=Mitglieder,ou=Groups,dc=example-church,dc=de")
                if members_group:
                    member_dns = members_group['attributes'].get('member', [])
                    for user in all_users:
                        if user['dn'].encode('utf-8') in member_dns or user['dn'] in member_dns:
                            filtered_users.append(user)
            elif export_settings.user_filter == 'visitors':
                visitors_group = ldap.get_group(f"cn=Besucher,ou=Groups,dc=example-church,dc=de")
                if visitors_group:
                    visitor_dns = visitors_group['attributes'].get('member', [])
                    for user in all_users:
                        if user['dn'].encode('utf-8') in visitor_dns or user['dn'] in visitor_dns:
                            filtered_users.append(user)
            elif export_settings.user_filter == 'family_heads':
                for user in all_users:
                    children = ldap.list_users(parent_dn=user['dn'])
                    if children:
                        filtered_users.append(user)

            # vCard für jeden Benutzer erstellen
            for user in filtered_users:
                attrs = user['attributes']

                # Dekodiere Felder
                given_name = attrs.get('givenName', [b''])[0]
                sn = attrs.get('sn', [b''])[0]
                mail = attrs.get('mail', [b''])[0]
                phone = attrs.get('telephoneNumber', [b''])[0]

                if isinstance(given_name, bytes):
                    given_name = given_name.decode('utf-8')
                if isinstance(sn, bytes):
                    sn = sn.decode('utf-8')
                if isinstance(mail, bytes):
                    mail = mail.decode('utf-8')
                if isinstance(phone, bytes):
                    phone = phone.decode('utf-8')

                # vCard erstellen
                vcard = vobject.vCard()

                if export_settings.include_name:
                    vcard.add('fn')
                    vcard.fn.value = f"{given_name} {sn}"

                    vcard.add('n')
                    vcard.n.value = vobject.vcard.Name(family=sn, given=given_name)

                if export_settings.include_email and mail:
                    vcard.add('email')
                    vcard.email.value = mail
                    vcard.email.type_param = 'INTERNET'

                if export_settings.include_phone and phone:
                    vcard.add('tel')
                    vcard.tel.value = phone
                    vcard.tel.type_param = 'CELL'

                vcard.add('org')
                vcard.org.value = ['Beispielgemeinde']

                vcards.append(vcard.serialize())

    except Exception as e:
        messages.error(request, f'Fehler beim Laden der Daten: {str(e)}')
        return redirect('member_list_export')

    # vCard-Datei erstellen
    response = HttpResponse('\n'.join(vcards), content_type='text/vcard; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="gemeindeliste.vcf"'

    return response


@login_required
@user_passes_test(is_ldap_admin)
def member_list_export_settings(request):
    """
    Admin-View: Export-Einstellungen verwalten
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete':
            # Lösche Export-Einstellung
            settings_id = request.POST.get('settings_id')
            try:
                export_settings = MemberListExportSettings.objects.get(pk=settings_id)
                export_settings.delete()
                messages.success(request, 'Export-Einstellungen gelöscht!')
            except MemberListExportSettings.DoesNotExist:
                messages.error(request, 'Export-Einstellungen nicht gefunden.')

        else:
            # Neue Konfiguration erstellen oder bearbeiten
            settings_id = request.POST.get('settings_id')

            if settings_id:
                # Bearbeiten
                export_settings = MemberListExportSettings.objects.get(pk=settings_id)
            else:
                # Neu erstellen
                export_settings = MemberListExportSettings()
                export_settings.created_by = request.user

            # Felder aktualisieren
            export_settings.name = request.POST.get('name')
            export_settings.description = request.POST.get('description', '')
            export_settings.include_name = request.POST.get('include_name') == 'on'
            export_settings.include_email = request.POST.get('include_email') == 'on'
            export_settings.include_phone = request.POST.get('include_phone') == 'on'
            export_settings.include_address = request.POST.get('include_address') == 'on'
            export_settings.include_birthday = request.POST.get('include_birthday') == 'on'
            export_settings.include_groups = request.POST.get('include_groups') == 'on'
            export_settings.include_family = request.POST.get('include_family') == 'on'
            export_settings.user_filter = request.POST.get('user_filter')
            export_settings.sort_by = request.POST.get('sort_by')
            export_settings.is_public = request.POST.get('is_public') == 'on'

            export_settings.save()

            messages.success(request, 'Export-Einstellungen gespeichert!')

        return redirect('member_list_export_settings')

    # Alle Konfigurationen anzeigen
    all_settings = MemberListExportSettings.objects.all()

    context = {
        'all_settings': all_settings,
    }

    return render(request, 'ldap/member_list_export_settings.html', context)
