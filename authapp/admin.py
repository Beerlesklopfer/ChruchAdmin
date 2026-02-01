from django.contrib import admin
from .models import LDAPConfig, LDAPUserLog, MemberListExportSettings, PermissionMapping, EmailTemplate

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User, Group
from django.contrib.admin import AdminSite
from django_auth_ldap.backend import LDAPBackend
from django.http import HttpResponseRedirect
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
import ldap

class LDAPUserAdmin(UserAdmin):
    """Erweiterter User Admin mit LDAP Funktionen"""
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_ldap_user', 'last_login')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    actions = ['sync_ldap_users', 'check_ldap_access']
    
    def is_ldap_user(self, obj):
        """Prüft ob Benutzer aus LDAP stammt"""
        try:
            ldap_user = LDAPBackend().populate_user(obj.username)
            return ldap_user is not None
        except:
            return False
    is_ldap_user.boolean = True
    is_ldap_user.short_description = 'LDAP User'
    
    def get_queryset(self, request):
        """Optimierte Query mit Prefetch"""
        qs = super().get_queryset(request)
        return qs.prefetch_related('groups')
    
    def sync_ldap_users(self, request, queryset):
        """Sync ausgewählte Benutzer mit LDAP"""
        success_count = 0
        error_count = 0
        
        for user in queryset:
            try:
                ldap_backend = LDAPBackend()
                ldap_user = ldap_backend.populate_user(user.username)
                
                if ldap_user:
                    # Aktualisiere Benutzerdaten aus LDAP
                    user.email = ldap_user.email
                    user.first_name = ldap_user.first_name
                    user.last_name = ldap_user.last_name
                    user.save()
                    success_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                self.message_user(
                    request, 
                    f"Fehler bei {user.username}: {str(e)}", 
                    messages.ERROR
                )
                error_count += 1
        
        if success_count > 0:
            self.message_user(
                request, 
                f"{success_count} Benutzer erfolgreich mit LDAP synchronisiert", 
                messages.SUCCESS
            )
        if error_count > 0:
            self.message_user(
                request, 
                f"{error_count} Benutzer konnten nicht synchronisiert werden", 
                messages.WARNING
            )
    
    sync_ldap_users.short_description = "Ausgewählte Benutzer mit LDAP synchronisieren"
    
    def check_ldap_access(self, request, queryset):
        """Prüft LDAP Zugriff für ausgewählte Benutzer"""
        for user in queryset:
            try:
                ldap_backend = LDAPBackend()
                # Versuche den Benutzer zu authentifizieren
                test_user = ldap_backend.authenticate(
                    request, 
                    username=user.username, 
                    password="dummy"  # Nur für Verbindungstest
                )
                
                if test_user:
                    self.message_user(
                        request, 
                        f"✓ {user.username}: LDAP Zugriff OK", 
                        messages.SUCCESS
                    )
                else:
                    self.message_user(
                        request, 
                        f"✗ {user.username}: Kein LDAP Zugriff", 
                        messages.WARNING
                    )
                    
            except Exception as e:
                self.message_user(
                    request, 
                    f"✗ {user.username}: LDAP Fehler - {str(e)}", 
                    messages.ERROR
                )
    
    check_ldap_access.short_description = "LDAP Zugriff prüfen"

@admin.register(LDAPConfig)
class LDAPConfigAdmin(admin.ModelAdmin):
    """Admin für LDAP Konfiguration"""
    list_display = ('name', 'server_uri', 'is_active', 'connection_status', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'server_uri', 'bind_dn')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['test_connection', 'activate_config', 'deactivate_config']

    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'is_active'),
            'description': 'Grundlegende Einstellungen für die LDAP-Verbindung'
        }),
        ('Verbindungsdetails', {
            'fields': ('server_uri', 'bind_dn', 'bind_password'),
            'description': 'LDAP Server-Verbindungsparameter. Beispiel Server URI: ldaps://ldap.example.com:636'
        }),
        ('Suchbasis', {
            'fields': ('user_search_base', 'user_search_filter', 'group_search_base'),
            'description': 'LDAP-Suchparameter für Benutzer und Gruppen'
        }),
        ('Attribut-Mapping', {
            'fields': ('attribute_mapping',),
            'description': 'JSON-Format für Attribut-Zuordnung. Beispiel: {"first_name": "givenName", "last_name": "sn", "email": "mail"}'
        }),
        ('Metadaten', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def get_form(self, request, obj=None, **kwargs):
        """Passwortfeld als Passwort-Widget anzeigen"""
        from django import forms
        form = super().get_form(request, obj, **kwargs)
        if 'bind_password' in form.base_fields:
            form.base_fields['bind_password'].widget = forms.PasswordInput(
                attrs={'placeholder': '••••••••' if obj else 'Passwort eingeben'}
            )
            form.base_fields['bind_password'].help_text = 'Bind-Passwort für LDAP-Authentifizierung (wird verschlüsselt gespeichert)'
        return form

    def connection_status(self, obj):
        """Zeigt den Verbindungsstatus an"""
        if not obj.is_active:
            return '⚫ Inaktiv'
        try:
            import ldap
            conn = ldap.initialize(obj.server_uri)
            conn.simple_bind_s(obj.bind_dn, obj.bind_password)
            conn.unbind()
            return '✓ Verbunden'
        except Exception as e:
            return f'✗ Fehler'
    connection_status.short_description = 'Status'

    def test_connection(self, request, queryset):
        """Teste LDAP-Verbindung für ausgewählte Konfigurationen"""
        import ldap as ldap_lib
        for config in queryset:
            try:
                conn = ldap_lib.initialize(config.server_uri)
                conn.simple_bind_s(config.bind_dn, config.bind_password)

                # Teste Benutzersuche
                users = conn.search_s(
                    config.user_search_base,
                    ldap_lib.SCOPE_SUBTREE,
                    config.user_search_filter.replace('%(user)s', '*'),
                    ['cn']
                )

                conn.unbind()
                self.message_user(
                    request,
                    f'✓ {config.name}: Verbindung erfolgreich! {len(users)} Benutzer gefunden.',
                    messages.SUCCESS
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'✗ {config.name}: Verbindungsfehler - {str(e)}',
                    messages.ERROR
                )
    test_connection.short_description = 'Verbindung testen'

    def activate_config(self, request, queryset):
        """Aktiviere ausgewählte Konfigurationen"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} Konfiguration(en) aktiviert', messages.SUCCESS)
    activate_config.short_description = 'Ausgewählte Konfigurationen aktivieren'

    def deactivate_config(self, request, queryset):
        """Deaktiviere ausgewählte Konfigurationen"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} Konfiguration(en) deaktiviert', messages.SUCCESS)
    deactivate_config.short_description = 'Ausgewählte Konfigurationen deaktivieren'

    def get_readonly_fields(self, request, obj=None):
        """Zeige created_at nur bei bestehenden Objekten"""
        if obj:
            return self.readonly_fields + ('created_at', 'updated_at')
        return self.readonly_fields

@admin.register(LDAPUserLog)
class LDAPUserLogAdmin(admin.ModelAdmin):

    """Admin für LDAP Logs"""
    list_display = ('user', 'action', 'ip_address', 'timestamp')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'details', 'ip_address')
    readonly_fields = ('user', 'action', 'details', 'ip_address', 'timestamp')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        """Verhindere manuelles Hinzufügen von Logs"""
        return False

    def has_change_permission(self, request, obj=None):
        """Verhindere Änderungen an Logs"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Erlaube Löschen nur Superusern"""
        return request.user.is_superuser


@admin.register(MemberListExportSettings)
class MemberListExportSettingsAdmin(admin.ModelAdmin):
    """Admin für Export-Einstellungen der Gemeindeliste"""
    list_display = ('name', 'user_filter', 'sort_by', 'is_public', 'created_by', 'created_at')
    list_filter = ('is_public', 'user_filter', 'sort_by', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'created_by')

    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'description', 'is_public')
        }),
        ('Export-Felder', {
            'fields': (
                'include_name',
                'include_email',
                'include_phone',
                'include_address',
                'include_birthday',
                'include_groups',
                'include_family'
            ),
            'description': 'Wählen Sie die Felder aus, die im Export enthalten sein sollen'
        }),
        ('Filter & Sortierung', {
            'fields': ('user_filter', 'sort_by'),
            'description': 'Definieren Sie welche Benutzer exportiert werden sollen'
        }),
        ('Metadaten', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def save_model(self, request, obj, form, change):
        """Setze created_by automatisch"""
        if not change:  # Nur bei Erstellung
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PermissionMapping)
class PermissionMappingAdmin(admin.ModelAdmin):
    """Admin für Berechtigungs-Zuordnungen"""
    list_display = ('permission_display', 'group_name', 'is_active', 'created_by', 'created_at')
    list_filter = ('permission', 'is_active', 'created_at')
    search_fields = ('group_name', 'permission')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    list_editable = ('is_active',)

    fieldsets = (
        ('Zuordnung', {
            'fields': ('permission', 'group_name', 'is_active')
        }),
        ('Metadaten', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def permission_display(self, obj):
        return obj.get_permission_display()
    permission_display.short_description = 'Berechtigung'
    permission_display.admin_order_field = 'permission'

    def save_model(self, request, obj, form, change):
        """Setze created_by automatisch"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    """Admin für E-Mail-Vorlagen"""
    list_display = ('name', 'template_type_display', 'is_active', 'send_automatically', 'updated_at')
    list_filter = ('template_type', 'is_active', 'send_automatically', 'created_at')
    search_fields = ('name', 'subject', 'body')
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active', 'send_automatically')

    fieldsets = (
        ('Allgemein', {
            'fields': ('name', 'template_type', 'is_active', 'send_automatically')
        }),
        ('E-Mail-Inhalt', {
            'fields': ('subject', 'body'),
            'description': 'Verwenden Sie Platzhalter wie {{name}}, {{email}}, {{username}}, {{first_name}}, {{last_name}}'
        }),
        ('Metadaten', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def template_type_display(self, obj):
        return obj.get_template_type_display()
    template_type_display.short_description = 'Vorlagentyp'
    template_type_display.admin_order_field = 'template_type'


class ChurchAdminSite(AdminSite):
    """Custom Admin Site mit LDAP Funktionen"""
    
    site_header = "ChurchAdmin Administration"
    site_title = "ChurchAdmin"
    index_title = "Willkommen in der ChurchAdmin Administration"
    
    def get_urls(self):
        """Füge custom URLs hinzu"""
        urls = super().get_urls()
        custom_urls = [
            path('ldap-test/', self.admin_view(self.ldap_test_view), name='ldap-test'),
            path('ldap-stats/', self.admin_view(self.ldap_stats_view), name='ldap-stats'),
        ]
        return custom_urls + urls
    
    def ldap_test_view(self, request):
        """LDAP Verbindungstest"""
        from django.conf import settings
        
        context = {
            **self.each_context(request),
            'title': 'LDAP Verbindungstest'
        }
        
        if request.method == 'POST':
            try:
                # Teste LDAP Verbindung
                conn = ldap.initialize(getattr(settings, 'AUTH_LDAP_SERVER_URI', ''))
                conn.simple_bind_s(
                    getattr(settings, 'AUTH_LDAP_BIND_DN', ''),
                    getattr(settings, 'AUTH_LDAP_BIND_PASSWORD', '')
                )
                
                # Teste Benutzersuche
                search_base = getattr(settings, 'AUTH_LDAP_USER_SEARCH', None)
                if search_base:
                    conn.search_s(
                        search_base.search_base,
                        ldap.SCOPE_BASE,
                        '(objectClass=*)'
                    )
                
                conn.unbind()
                messages.success(request, "✓ LDAP Verbindung erfolgreich!")
                
            except Exception as e:
                messages.error(request, f"✗ LDAP Fehler: {str(e)}")
        
        return render(request, 'admin/ldap_test.html', context)
    
    def ldap_stats_view(self, request):
        """LDAP Statistik"""
        from django.conf import settings
        
        context = {
            **self.each_context(request),
            'title': 'LDAP Statistik'
        }
        
        stats = {}
        try:
            conn = ldap.initialize(getattr(settings, 'AUTH_LDAP_SERVER_URI', ''))
            conn.simple_bind_s(
                getattr(settings, 'AUTH_LDAP_BIND_DN', ''),
                getattr(settings, 'AUTH_LDAP_BIND_PASSWORD', '')
            )
            
            # Benutzer zählen
            user_search = getattr(settings, 'AUTH_LDAP_USER_SEARCH', None)
            if user_search:
                users = conn.search_s(
                    user_search.search_base,
                    ldap.SCOPE_SUBTREE,
                    user_search.filterstr.replace('%(user)s', '*')
                )
                stats['total_users'] = len([u for u in users if u[0]])
            
            # Gruppen zählen
            group_search = getattr(settings, 'AUTH_LDAP_GROUP_SEARCH', None)
            if group_search:
                groups = conn.search_s(
                    group_search.search_base,
                    ldap.SCOPE_SUBTREE,
                    group_search.filterstr
                )
                stats['total_groups'] = len([g for g in groups if g[0]])
            
            conn.unbind()
            
        except Exception as e:
            messages.error(request, f"LDAP Fehler: {str(e)}")
            stats = {'error': str(e)}
        
        context['stats'] = stats
        return render(request, 'admin/ldap_stats.html', context)

# Custom Admin Site registrieren
church_admin_site = ChurchAdminSite(name='churchadmin')

# Models bei custom Admin registrieren
# User Admin registrieren
admin.site.unregister(User)
admin.site.unregister(Group)

admin.site.register(User, LDAPUserAdmin)

church_admin_site.register(User, LDAPUserAdmin)
church_admin_site.register(LDAPConfig, LDAPConfigAdmin)
church_admin_site.register(LDAPUserLog, LDAPUserLogAdmin)
church_admin_site.register(MemberListExportSettings, MemberListExportSettingsAdmin)
church_admin_site.register(PermissionMapping, PermissionMappingAdmin)
church_admin_site.register(EmailTemplate, EmailTemplateAdmin)

