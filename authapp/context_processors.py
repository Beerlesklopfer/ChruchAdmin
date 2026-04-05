def church_settings(request):
    """Stellt globale Gemeinde-Einstellungen fuer alle Templates bereit."""
    from authapp.models import AppSettings
    return {
        'church_name': AppSettings.get('church_name', 'Bibelgemeinde Lage'),
        'church_domain': AppSettings.get('church_domain', 'bibelgemeinde-lage.de'),
        'church_address': AppSettings.get('church_address', ''),
        'church_phone': AppSettings.get('church_phone', ''),
        'church_email': AppSettings.get('church_email', ''),
        'church_contact_person': AppSettings.get('church_contact_person', ''),
        'privacy_contact_person': AppSettings.get('privacy_contact_person', ''),
    }


def user_permissions(request):
    """Stellt Berechtigungs-Flags fuer alle Templates bereit."""
    if not request.user.is_authenticated:
        return {'is_ldap_admin': False, 'can_manage_ldap': False}

    from authapp.views import is_ldap_admin, has_permission
    admin = is_ldap_admin(request.user)
    # Sekretariat und andere mit edit_members duerfen die LDAP-Verwaltung sehen
    can_manage = admin or has_permission(request.user, 'edit_members')
    can_send_massmail = admin or has_permission(request.user, 'send_massmail')
    can_export = admin or has_permission(request.user, 'export_members')
    return {
        'is_ldap_admin': admin,
        'can_manage_ldap': can_manage,
        'can_send_massmail': can_send_massmail,
        'can_export_members': can_export,
        'show_tools_menu': can_send_massmail or can_export,
    }
