from django.urls import path, include
from django.contrib import admin
from authapp import views as auth_views
from authapp import export_views
from authapp import permissions_views
from authapp import password_reset_views
from authapp import autoconfig_views
from authapp import mail_admin_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('captcha/', include('captcha.urls')),
    path('ldap/mailing/', include('mailing.urls')),
    path('datenschutz/', include('privacy.urls')),
    path('tickets/', include('tickets.urls')),
    path('hilfe/', include('helpcenter.urls')),
    path('notizen/', include('personnotes.urls')),
    path('', auth_views.home, name='home'),
    path('login/', auth_views.ldap_login, name='login'),
    path('logout/', auth_views.custom_logout, name='logout'),
    path('register/', auth_views.register, name='register'),
    path('register/verify/<str:token>/', auth_views.register_verify, name='register_verify'),
    path('ldap/registrations/', auth_views.registration_requests, name='registration_requests'),
    path('ldap/registrations/<int:pk>/approve/', auth_views.registration_approve, name='registration_approve'),
    path('ldap/registrations/<int:pk>/reject/', auth_views.registration_reject, name='registration_reject'),
    path('ldap/registrations/<int:pk>/edit/', auth_views.registration_edit, name='registration_edit'),
    path('ldap/registrations/<int:pk>/delete/', auth_views.registration_delete, name='registration_delete'),
    path('profile/', auth_views.profile, name='profile'),
    path('dashboard/', auth_views.user_dashboard, name='user_dashboard'),
    path('dashboard/family/', auth_views.family_manage, name='family_manage'),
    path('dashboard/family/<str:cn>/edit/', auth_views.family_member_edit, name='family_member_edit'),

    # LDAP URLs
    path('ldap/', auth_views.ldap_dashboard, name='ldap_dashboard'),
    path('ldap/admin/', auth_views.ldap_admin, name='ldap_admin'),
    path('ldap/users/', auth_views.ldap_user_search, name='ldap_user_search'),

    # Family Management URLs
    path('ldap/family-tree/', auth_views.family_tree, name='family_tree'),
    path('ldap/family/create/', auth_views.family_create, name='family_create'),
    path('ldap/family/<str:parent_cn>/add-member/', auth_views.family_add_member, name='family_add_member'),
    path('ldap/user/<str:cn>/edit/', auth_views.user_edit, name='user_edit'),
    path('ldap/user/create/', auth_views.user_create, name='user_create'),
    path('ldap/user/<str:cn>/delete/', auth_views.user_delete, name='user_delete'),

    # Member List Export URLs
    path('ldap/export/', export_views.member_list_export, name='member_list_export'),
    path('ldap/export/pdf/', export_views.member_list_export_pdf, name='member_list_export_pdf'),
    path('ldap/export/pdf/<int:settings_id>/', export_views.member_list_export_pdf, name='member_list_export_pdf_settings'),
    path('ldap/export/vcard/', export_views.member_list_export_vcard, name='member_list_export_vcard'),
    path('ldap/export/vcard/<int:settings_id>/', export_views.member_list_export_vcard, name='member_list_export_vcard_settings'),
    path('ldap/export/settings/', export_views.member_list_export_settings, name='member_list_export_settings'),

    # Permissions Management URLs
    path('ldap/permissions/', permissions_views.permissions_overview, name='permissions_overview'),
    path('ldap/permissions/matrix/', permissions_views.permissions_matrix, name='permissions_matrix'),
    path('ldap/permissions/matrix/edit/', permissions_views.permissions_matrix_edit, name='permissions_matrix_edit'),
    path('ldap/my-permissions/', permissions_views.my_permissions, name='my_permissions'),

    # Password Reset URLs
    path('password-reset/', password_reset_views.password_reset_request, name='password_reset_request'),
    path('password-reset/confirm/<str:token>/', password_reset_views.password_reset_confirm, name='password_reset_confirm'),

    # Group Management URLs
    path('ldap/groups/', auth_views.group_list, name='group_list'),
    path('ldap/groups/create/', auth_views.group_create, name='group_create'),
    path('ldap/groups/<str:group_cn>/', auth_views.group_detail, name='group_detail'),
    path('ldap/groups/<str:group_cn>/edit/', auth_views.group_edit, name='group_edit'),
    path('ldap/groups/<str:group_cn>/delete/', auth_views.group_delete, name='group_delete'),
    path('ldap/groups/<str:group_cn>/add-member/', auth_views.group_add_member, name='group_add_member'),
    path('ldap/groups/<str:group_cn>/remove-member/', auth_views.group_remove_member, name='group_remove_member'),

    # Member Management URLs
    path('ldap/member/add/', auth_views.member_add, name='member_add'),
    path('ldap/member/add-existing/', auth_views.member_add_existing, name='member_add_existing'),

    # Geraete-Konfiguration URLs
    path('profile/mobileconfig/', autoconfig_views.download_mobileconfig, name='download_mobileconfig'),
    path('profile/android-setup/', autoconfig_views.android_setup, name='android_setup'),

    # WiFi-Netzwerk Admin URLs
    path('ldap/wifi/', autoconfig_views.wifi_network_list, name='wifi_network_list'),
    path('ldap/wifi/create/', autoconfig_views.wifi_network_edit, name='wifi_network_create'),
    path('ldap/wifi/<int:pk>/edit/', autoconfig_views.wifi_network_edit, name='wifi_network_edit'),
    path('ldap/wifi/<int:pk>/delete/', autoconfig_views.wifi_network_delete, name='wifi_network_delete'),
    path('ldap/wifi/<int:pk>/print/', autoconfig_views.wifi_network_print, name='wifi_network_print'),

    # Mail-Verwaltung (Phase 6)
    path('ldap/mail/', mail_admin_views.mail_overview, name='mail_overview'),
    path('ldap/mail/domains/', mail_admin_views.mail_domain_list, name='mail_domain_list'),
    path('ldap/mail/domains/create/', mail_admin_views.mail_domain_create, name='mail_domain_create'),
    path('ldap/mail/domains/<str:domain_name>/edit/', mail_admin_views.mail_domain_edit, name='mail_domain_edit'),
    path('ldap/mail/domains/<str:domain_name>/delete/', mail_admin_views.mail_domain_delete, name='mail_domain_delete'),
    path('ldap/mail/groups/', mail_admin_views.mail_group_list, name='mail_group_list'),
    path('ldap/mail/groups/create/', mail_admin_views.mail_group_create, name='mail_group_create'),
    path('ldap/mail/groups/<str:b64dn>/edit/', mail_admin_views.mail_group_edit, name='mail_group_edit'),
    path('ldap/mail/groups/<str:b64dn>/toggle/', mail_admin_views.mail_group_toggle_enabled, name='mail_group_toggle'),
    path('ldap/mail/groups/<str:b64dn>/delete/', mail_admin_views.mail_group_delete, name='mail_group_delete'),
    path('ldap/mail/bulk/', mail_admin_views.mail_bulk, name='mail_bulk'),

    # Backup Management URLs
    path('ldap/backup/', auth_views.backup_dashboard, name='backup_dashboard'),
    path('ldap/backup/<int:backup_id>/download/', auth_views.backup_download, name='backup_download'),
    path('ldap/backup/<int:backup_id>/delete/', auth_views.backup_delete, name='backup_delete'),
    path('ldap/backup/cleanup/', auth_views.backup_cleanup, name='backup_cleanup'),
    path('ldap/backup/<int:backup_id>/restore/', auth_views.backup_restore, name='backup_restore'),
]