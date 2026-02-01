"""
Gemeindelisten-Export Views
PDF und vCard/CardDAV Export
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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
            'user_filter': 'all',
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
            else:  # all
                filtered_users = all_users

            # Sortierung
            sort_field = export_settings.sort_by
            filtered_users.sort(key=lambda u: u['attributes'].get(sort_field, [b''])[0].decode('utf-8') if isinstance(u['attributes'].get(sort_field, [b''])[0], bytes) else u['attributes'].get(sort_field, [''])[0])

            # Daten extrahieren
            for user in filtered_users:
                attrs = user['attributes']

                # Dekodiere Basis-Felder
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

                user_dict = {}

                if export_settings.include_name:
                    user_dict['name'] = f"{given_name} {sn}"
                if export_settings.include_email:
                    user_dict['email'] = mail
                if export_settings.include_phone:
                    user_dict['phone'] = phone

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

    # PDF-Dokument
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1c2647'),
        alignment=TA_CENTER,
        spaceAfter=30,
    )

    # Titel
    elements.append(Paragraph("Gemeindeliste - Beispielgemeinde", title_style))
    elements.append(Paragraph(f"Export: {export_settings.name}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

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
        if export_settings.include_groups:
            row.append(user.get('groups', ''))
        table_data.append(row)

    # Tabelle stylen
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1c2647')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f7f3e6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f3e6')]),
    ]))

    elements.append(table)

    # PDF bauen
    doc.build(elements)

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
            'user_filter': 'all',
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
