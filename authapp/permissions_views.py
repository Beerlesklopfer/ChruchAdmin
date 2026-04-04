"""
Rechtemanagement Views
Verwaltung von Berechtigungen und LDAP-Gruppen-Zuordnungen
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from authapp.views import is_ldap_admin, has_permission
from main.ldap_manager import LDAPManager


@login_required
@user_passes_test(is_ldap_admin)
def permissions_overview(request):
    """
    Übersicht über alle Berechtigungen und Gruppenzuordnungen
    """
    # Definierte Berechtigungen und ihre Beschreibungen
    permissions_config = {
        'manage_users': {
            'name': 'Benutzer verwalten',
            'description': 'Benutzer erstellen, bearbeiten und löschen',
            'groups': ['Leitung', 'Admins', 'Pastor'],
            'icon': 'people',
            'color': 'danger'
        },
        'manage_groups': {
            'name': 'Gruppen verwalten',
            'description': 'LDAP-Gruppen erstellen und verwalten',
            'groups': ['Leitung', 'Admins'],
            'icon': 'diagram-2',
            'color': 'warning'
        },
        'manage_families': {
            'name': 'Familien verwalten',
            'description': 'Familien erstellen und Mitglieder hinzufügen',
            'groups': ['Leitung', 'Admins', 'Pastor', 'Familienpflege', 'Sekretariat'],
            'icon': 'diagram-3',
            'color': 'info'
        },
        'manage_mail': {
            'name': 'Mail-Verwaltung',
            'description': 'E-Mail-Adressen und Weiterleitungen verwalten',
            'groups': ['Leitung', 'Admins'],
            'icon': 'envelope',
            'color': 'primary'
        },
        'manage_mail_domains': {
            'name': 'Mail-Domains verwalten',
            'description': 'Mail-Domains erstellen und verwalten',
            'groups': ['Leitung', 'Admins'],
            'icon': 'globe',
            'color': 'primary'
        },
        'view_members': {
            'name': 'Gemeindeliste ansehen',
            'description': 'Mitgliederliste und Kontaktdaten einsehen',
            'groups': ['Leitung', 'Admins', 'Pastor', 'Mitglieder', 'Mitarbeiter', 'Sekretariat'],
            'icon': 'eye',
            'color': 'success'
        },
        'edit_members': {
            'name': 'Gemeindeliste bearbeiten',
            'description': 'Mitgliederdaten bearbeiten und aktualisieren',
            'groups': ['Leitung', 'Admins', 'Pastor', 'Gemeindemitarbeiter', 'Sekretariat'],
            'icon': 'pencil',
            'color': 'warning'
        },
        'export_members': {
            'name': 'Gemeindeliste exportieren',
            'description': 'Mitgliederlisten als PDF oder vCard exportieren',
            'groups': ['Leitung', 'Admins', 'Pastor', 'Sekretariat', 'Mitarbeiter'],
            'icon': 'download',
            'color': 'info'
        },
    }

    # Hole alle LDAP-Gruppen
    ldap_groups = []
    try:
        with LDAPManager() as ldap:
            groups = ldap.list_groups()
            for group in groups:
                cn = group['attributes'].get('cn', [b''])[0]
                if isinstance(cn, bytes):
                    cn = cn.decode('utf-8')

                description = group['attributes'].get('description', [b''])[0]
                if isinstance(description, bytes):
                    description = description.decode('utf-8')

                # Zähle Mitglieder
                members = group['attributes'].get('member', [])
                member_count = len([m for m in members if m != 'cn=nobody' and m != b'cn=nobody'])

                # Prüfe welche Berechtigungen diese Gruppe hat
                group_permissions = []
                for perm_key, perm_config in permissions_config.items():
                    if cn in perm_config['groups']:
                        group_permissions.append({
                            'key': perm_key,
                            'name': perm_config['name'],
                            'icon': perm_config['icon']
                        })

                ldap_groups.append({
                    'cn': cn,
                    'dn': group['dn'],
                    'description': description,
                    'member_count': member_count,
                    'permissions': group_permissions,
                })
    except Exception as e:
        messages.error(request, f'Fehler beim Laden der LDAP-Gruppen: {str(e)}')

    context = {
        'permissions_config': permissions_config,
        'ldap_groups': ldap_groups,
    }

    return render(request, 'ldap/permissions_overview.html', context)


@login_required
@user_passes_test(is_ldap_admin)
def permissions_matrix(request):
    """
    Matrix-Ansicht: Zeigt alle Berechtigungen vs. alle Gruppen
    Ermöglicht Admins die Bearbeitung der Zuordnungen
    """
    from authapp.models import PermissionMapping
    permissions = dict(PermissionMapping.PERMISSION_CHOICES)

    # Berechtigungs-Mapping aus Datenbank laden
    permission_groups = {}
    for perm_key in permissions.keys():
        permission_groups[perm_key] = PermissionMapping.get_groups_for_permission(perm_key)

    # Hole alle LDAP-Gruppen
    ldap_groups = []
    ldap_error = None

    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info('Attempting to load LDAP groups...')
        with LDAPManager() as ldap:
            groups = ldap.list_groups()
            logger.info(f'LDAP returned {len(groups)} groups')
            for group in groups:
                cn = group['attributes'].get('cn', [b''])[0]
                if isinstance(cn, bytes):
                    cn = cn.decode('utf-8')
                if cn and cn != 'nobody':  # Filter out empty and nobody group
                    ldap_groups.append(cn)
                    logger.info(f'Added group: {cn}')
        logger.info(f'Successfully loaded {len(ldap_groups)} LDAP groups')
    except Exception as e:
        ldap_error = str(e)
        logger.error(f'LDAP-Fehler beim Laden der Gruppen: {e}', exc_info=True)
        messages.warning(request, f'LDAP-Gruppen konnten nicht geladen werden. Es werden die konfigurierten Gruppen aus der Datenbank angezeigt.')

    # Wenn keine LDAP-Gruppen gefunden wurden, verwende alle Gruppen aus PermissionMapping
    if not ldap_groups:
        logger.warning('No LDAP groups found, trying fallback to PermissionMapping')
        all_groups = set()
        for groups_list in permission_groups.values():
            all_groups.update(groups_list)
        ldap_groups = sorted(list(all_groups))
        logger.info(f'Fallback 1: Loaded {len(ldap_groups)} groups from PermissionMapping: {ldap_groups}')

    # Falls immer noch leer, verwende Fallback-Standardgruppen
    if not ldap_groups:
        logger.warning('Still no groups found, using hardcoded fallback')
        ldap_groups = ['Leitung', 'Admins', 'Pastor', 'Mitglieder', 'Mitarbeiter',
                      'Sekretariat', 'Familienpflege', 'Gemeindemitarbeiter']
        messages.info(request, 'Standard-Gruppen werden angezeigt. Bitte überprüfen Sie die LDAP-Verbindung.')
        logger.info(f'Fallback 2: Using {len(ldap_groups)} hardcoded groups')

    # Sortiere Gruppen alphabetisch
    ldap_groups.sort()
    logger.info(f'Final ldap_groups count before rendering: {len(ldap_groups)}')

    # Erstelle Matrix
    matrix = []
    for perm_key, perm_name in permissions.items():
        row = {
            'permission': perm_name,
            'key': perm_key,
            'groups': {}
        }
        for group in ldap_groups:
            row['groups'][group] = group in permission_groups.get(perm_key, [])
        matrix.append(row)

    context = {
        'matrix': matrix,
        'ldap_groups': ldap_groups,
        'ldap_error': ldap_error,
        'is_editable': request.user.is_superuser or is_ldap_admin(request.user),
    }

    logger.info(f'Context prepared with {len(ldap_groups)} groups: {ldap_groups}')
    logger.info(f'Matrix has {len(matrix)} rows')
    logger.info(f'is_editable: {context["is_editable"]}')

    return render(request, 'ldap/permissions_matrix.html', context)


@login_required
def my_permissions(request):
    """
    Zeigt dem Benutzer seine eigenen Berechtigungen
    """
    user_permissions = []

    from authapp.models import PermissionMapping
    perm_icons = {
        'manage_users': 'people',
        'manage_groups': 'diagram-2',
        'manage_families': 'diagram-3',
        'manage_mail': 'envelope',
        'manage_mail_domains': 'globe',
        'send_massmail': 'megaphone',
        'manage_registrations': 'person-plus',
        'view_members': 'eye',
        'edit_members': 'pencil',
        'export_members': 'download',
    }
    permissions_config = {}
    for key, name in PermissionMapping.PERMISSION_CHOICES:
        permissions_config[key] = {'name': name, 'icon': perm_icons.get(key, 'key')}

    for perm_key, perm_config in permissions_config.items():
        has_perm = has_permission(request.user, perm_key)
        user_permissions.append({
            'key': perm_key,
            'name': perm_config['name'],
            'icon': perm_config['icon'],
            'granted': has_perm,
        })

    # Hole Gruppenmitgliedschaften
    user_groups = []
    try:
        with LDAPManager() as ldap:
            user_data = ldap.get_user(request.user.username)
            if user_data:
                member_of = user_data['attributes'].get('memberOf', [])
                for group_dn in member_of:
                    if isinstance(group_dn, bytes):
                        group_dn = group_dn.decode('utf-8')

                    import re
                    match = re.search(r'cn=([^,]+)', group_dn)
                    if match:
                        user_groups.append(match.group(1))
    except:
        pass

    context = {
        'user_permissions': user_permissions,
        'user_groups': user_groups,
        'is_admin': request.user.is_superuser or is_ldap_admin(request.user),
    }

    return render(request, 'ldap/my_permissions.html', context)


@login_required
@user_passes_test(is_ldap_admin)
def permissions_matrix_edit(request):
    """
    AJAX-Endpoint zum Bearbeiten der Berechtigungs-Matrix
    Nur für Admins
    """
    from django.http import JsonResponse
    import json

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Nur POST erlaubt'}, status=400)

    try:
        data = json.loads(request.body)
        permission_key = data.get('permission')
        group_name = data.get('group')
        enabled = data.get('enabled', False)

        # Validierung
        from authapp.models import PermissionMapping
        valid_permissions = [key for key, _ in PermissionMapping.PERMISSION_CHOICES]

        if permission_key not in valid_permissions:
            return JsonResponse({'success': False, 'error': 'Ungültige Berechtigung'}, status=400)

        if not group_name:
            return JsonResponse({'success': False, 'error': 'Gruppenname fehlt'}, status=400)

        # Speichere Änderung in Datenbank
        from authapp.models import PermissionMapping
        mapping = PermissionMapping.set_permission(
            permission=permission_key,
            group_name=group_name,
            enabled=enabled,
            created_by=request.user
        )

        # Keine Django Messages bei AJAX - nur JSON Response für Toast
        return JsonResponse({
            'success': True,
            'message': f'Berechtigung für "{group_name}" {"aktiviert" if enabled else "deaktiviert"}',
            'permission': permission_key,
            'group': group_name,
            'enabled': enabled,
            'mapping_id': mapping.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Ungültige JSON-Daten'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
